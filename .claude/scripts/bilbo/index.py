#!/usr/bin/env python3
# B.I.L.B.O. — Bot Indexing Local Binary Objects.
#
# The indexer. Not a reactive agent — a background/scheduled script (README:
# "runs in the background as a scheduled task"). Walks brain/, detects new or
# modified markdown files, chunks them, embeds the chunks, and stores the
# vectors in a local SQLite index. Bilbo only WRITES the index; a future
# S.A.M.W.I.S.E. reader will READ it (encode the query, cosine-rank the
# chunks) — that boundary is deliberate, see README.md's Bilbo/Samwise split.
#
# Deterministic except for the embedding model itself: no LLM call, embeddings
# are computed locally by sentence-transformers. Idempotent and incremental —
# unchanged files are skipped entirely (no re-embedding cost).
#
# Storage: brain/index/bilbo.db (SQLite). Outside brain/db/ on purpose — that
# folder is G.I.M.L.I.'s access monopoly (brain/db/CLAUDE.md). The index is
# derived data (regenerable from brain/ markdown) and is gitignored.
#
# Model pinning: the embedding model is pinned to a fixed HF Hub revision
# (commit hash), not the moving "main" branch, so a future re-download (e.g.
# on a new machine, or after --rebuild) can never silently swap in different
# weights and desync from vectors computed earlier. The (model, revision) pair
# actually used is recorded in the `meta` table; a mismatch at startup aborts
# with a clear error rather than silently mixing incompatible vector spaces.

import argparse
import hashlib
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# --- Model configuration -----------------------------------------------------
# Same model as prompt-vault (github.com/Jarkendar/prompt-vault) for
# consistency across projects: multilingual (PL/EN), 384-dim, small enough
# for a Pi-class target eventually.
DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# Pinned commit hash on the HF Hub for DEFAULT_MODEL_NAME (checked 2026-07-02).
# Override via BILBO_EMBED_REVISION only for a deliberate, documented migration
# — always follow with --rebuild, since old and new-revision vectors are not
# comparable.
DEFAULT_MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
EMBED_DIM = 384

# Corpus rules: exclude Smeagol's logs (not knowledge, and privacy-sensitive
# per SKILL.md), the index's own folder, and per-folder CLAUDE.md files (these
# are operating instructions for Claude Code, not retrievable knowledge).
EXCLUDED_DIR_PARTS = {"index"}
EXCLUDED_SUBPATHS = ("current/smeagol",)
EXCLUDED_FILENAMES = {"CLAUDE.md"}

SCHEMA_VERSION = "1"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
MAX_CHUNK_WORDS = 90  # keeps chunks well under this model's ~128-token window


# --- Environment --------------------------------------------------------------

def resolve_brain_path(project_dir: Path) -> Path:
    env_file = project_dir / ".claude" / "gandalf.env"
    raw = None
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("BRAIN_PATH="):
                raw = line.split("=", 1)[1].strip()
                break
    except OSError:
        pass
    if not raw:
        sys.exit("BILBO: BRAIN_PATH not set in .claude/gandalf.env — aborting.")
    path = Path(raw)
    if not path.is_absolute():
        path = project_dir / path
    path = path.resolve()
    if not path.is_dir():
        sys.exit(f"BILBO: resolved BRAIN_PATH does not exist: {path}")
    return path


# --- Discovery -----------------------------------------------------------------

def is_excluded(rel_path: Path) -> bool:
    parts = rel_path.parts
    if parts and parts[0] in EXCLUDED_DIR_PARTS:
        return True
    posix = rel_path.as_posix()
    if any(posix.startswith(sub) for sub in EXCLUDED_SUBPATHS):
        return True
    if rel_path.name in EXCLUDED_FILENAMES:
        return True
    return False


def discover_files(brain_dir: Path, scope: Path | None) -> list[Path]:
    root = scope if scope is not None else brain_dir
    if root.is_file():
        candidates = [root]
    else:
        candidates = root.rglob("*.md")
    found = []
    for p in candidates:
        if not p.is_file():
            continue
        rel = p.relative_to(brain_dir)
        if is_excluded(rel):
            continue
        found.append(rel)
    return sorted(found, key=lambda r: r.as_posix())


def file_hash(abs_path: Path) -> str:
    return hashlib.sha256(abs_path.read_bytes()).hexdigest()


# --- Chunking --------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_fm = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"')
    return fm, body


def split_by_heading(body: str) -> list[tuple[str, str]]:
    """Split body into (heading, section_text) blocks. Text before the first
    heading (if any) gets heading '' (preamble)."""
    lines = body.splitlines()
    blocks: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            if current_lines and any(l.strip() for l in current_lines):
                blocks.append((current_heading, current_lines))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and any(l.strip() for l in current_lines):
        blocks.append((current_heading, current_lines))
    return [(h, "\n".join(ls).strip()) for h, ls in blocks]


def split_into_windows(text: str, max_words: int) -> list[str]:
    """Split text into paragraph-aligned windows of at most max_words words.
    A single paragraph longer than max_words is hard-split by word count."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    windows: list[str] = []
    current: list[str] = []
    current_words = 0
    for para in paragraphs:
        para_words = para.split()
        if len(para_words) > max_words:
            if current:
                windows.append("\n\n".join(current))
                current, current_words = [], 0
            for i in range(0, len(para_words), max_words):
                windows.append(" ".join(para_words[i:i + max_words]))
            continue
        if current_words + len(para_words) > max_words and current:
            windows.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(para)
        current_words += len(para_words)
    if current:
        windows.append("\n\n".join(current))
    return windows


def chunk_markdown(rel_path: Path, text: str) -> list[tuple[str, str]]:
    """Return [(heading, chunk_text_with_context), ...] for one file."""
    fm, body = split_frontmatter(text)
    title = fm.get("title") or rel_path.stem
    blocks = split_by_heading(body)
    if not blocks:
        blocks = [("", body.strip())]

    chunks: list[tuple[str, str]] = []
    for heading, section_text in blocks:
        if not section_text:
            continue
        for window in split_into_windows(section_text, MAX_CHUNK_WORDS):
            display_heading = heading or title
            # Prefix with title + heading so the embedded text carries context
            # even once split out of the surrounding document.
            embed_text = f"{title}\n{display_heading}\n\n{window}" if heading else f"{title}\n\n{window}"
            chunks.append((display_heading, embed_text))
    return chunks


# --- Storage -----------------------------------------------------------------

def open_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            mtime REAL NOT NULL,
            chunk_count INTEGER NOT NULL,
            indexed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            ord INTEGER NOT NULL,
            heading TEXT,
            text TEXT NOT NULL,
            vector BLOB NOT NULL,
            token_count INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    conn.commit()
    return conn


def get_meta(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def set_meta(conn: sqlite3.Connection, **kwargs):
    conn.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(kwargs.items()),
    )
    conn.commit()


def check_model_consistency(conn: sqlite3.Connection, model_name: str, revision: str, rebuild: bool):
    meta = get_meta(conn)
    if not meta:
        return  # fresh DB, nothing to check yet
    prev_model = meta.get("model_name")
    prev_revision = meta.get("model_revision")
    prev_schema = meta.get("schema_version")
    if prev_schema and prev_schema != SCHEMA_VERSION and not rebuild:
        sys.exit(
            f"BILBO: index schema changed ({prev_schema} -> {SCHEMA_VERSION}). "
            f"Run with --rebuild."
        )
    if prev_model and (prev_model != model_name or prev_revision != revision) and not rebuild:
        sys.exit(
            f"BILBO: index was built with model={prev_model}@{prev_revision}, "
            f"but this run requests {model_name}@{revision}. Mixing vector "
            f"spaces would corrupt similarity search. Run with --rebuild to "
            f"re-embed everything under the new model, or drop "
            f"BILBO_EMBED_REVISION/--model to keep using the pinned default."
        )


def vector_to_blob(vec) -> bytes:
    return vec.astype("float32").tobytes()


# --- Sync ----------------------------------------------------------------

def sync(conn: sqlite3.Connection, brain_dir: Path, model_name: str, revision: str,
         scope: Path | None, dry_run: bool, rebuild: bool):
    disk_files = discover_files(brain_dir, scope)
    disk_set = {p.as_posix() for p in disk_files}

    scope_prefix = None
    if scope is not None:
        scope_prefix = scope.relative_to(brain_dir).as_posix() if scope != brain_dir else None

    existing = {} if rebuild else dict(
        conn.execute("SELECT path, content_hash FROM files").fetchall()
    )

    to_update: list[Path] = []
    skipped = 0
    for rel in disk_files:
        abs_path = brain_dir / rel
        h = file_hash(abs_path)
        posix = rel.as_posix()
        if existing.get(posix) == h:
            skipped += 1
            continue
        to_update.append(rel)

    to_delete = []
    if not rebuild:
        for posix in existing:
            if scope_prefix and not posix.startswith(scope_prefix):
                continue  # outside this partial run's scope — leave untouched
            if posix not in disk_set:
                to_delete.append(posix)

    if dry_run:
        print(f"BILBO (dry-run): {len(to_update)} to add/update, "
              f"{len(to_delete)} to delete, {skipped} unchanged.")
        for rel in to_update:
            print(f"  update: {rel.as_posix()}")
        for posix in to_delete:
            print(f"  delete: {posix}")
        return

    # Lazy-import: only pay the (heavy) sentence-transformers import cost when
    # there is actually work to embed, or when we need to touch the DB at all.
    total_chunks = 0
    if to_update:
        from sentence_transformers import SentenceTransformer

        print(f"BILBO: loading {model_name}@{revision} ...")
        model = SentenceTransformer(model_name, revision=revision)

        per_file_chunks: dict[str, list[tuple[str, str]]] = {}
        all_texts: list[str] = []
        for rel in to_update:
            abs_path = brain_dir / rel
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_markdown(rel, text)
            per_file_chunks[rel.as_posix()] = chunks
            all_texts.extend(text for _, text in chunks)

        vectors = []
        if all_texts:
            print(f"BILBO: embedding {len(all_texts)} chunks from {len(to_update)} file(s) ...")
            vectors = model.encode(
                all_texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True
            )

        cursor = 0
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for rel in to_update:
            posix = rel.as_posix()
            abs_path = brain_dir / rel
            h = file_hash(abs_path)
            chunks = per_file_chunks[posix]
            n = len(chunks)
            file_vectors = vectors[cursor:cursor + n]
            cursor += n

            conn.execute("DELETE FROM chunks WHERE path = ?", (posix,))
            for i, ((heading, text), vec) in enumerate(zip(chunks, file_vectors)):
                conn.execute(
                    "INSERT INTO chunks(path, ord, heading, text, vector, token_count) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (posix, i, heading, text, vector_to_blob(vec), len(text.split())),
                )
            conn.execute(
                "INSERT INTO files(path, content_hash, mtime, chunk_count, indexed_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET content_hash=excluded.content_hash, "
                "mtime=excluded.mtime, chunk_count=excluded.chunk_count, "
                "indexed_at=excluded.indexed_at",
                (posix, h, abs_path.stat().st_mtime, n, now),
            )
            total_chunks += n

        set_meta(
            conn,
            model_name=model_name,
            model_revision=revision,
            embed_dim=str(EMBED_DIM),
            schema_version=SCHEMA_VERSION,
        )

    for posix in to_delete:
        conn.execute("DELETE FROM chunks WHERE path = ?", (posix,))
        conn.execute("DELETE FROM files WHERE path = ?", (posix,))

    conn.commit()
    print(f"BILBO: {len(to_update)} file(s) updated ({total_chunks} chunks), "
          f"{len(to_delete)} deleted, {skipped} unchanged.")


# --- CLI -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="B.I.L.B.O. — embedding indexer for brain/")
    parser.add_argument("--rebuild", action="store_true", help="wipe and rebuild the full index")
    parser.add_argument("--path", type=str, default=None,
                         help="limit to one file or subdirectory (relative to BRAIN_PATH)")
    parser.add_argument("--model", type=str, default=None, help="override the embedding model name")
    parser.add_argument("--dry-run", action="store_true", help="report deltas without embedding or writing")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parents[3]
    brain_dir = resolve_brain_path(project_dir)

    model_name = args.model or os.environ.get("BILBO_EMBED_MODEL", DEFAULT_MODEL_NAME)
    revision = os.environ.get("BILBO_EMBED_REVISION", DEFAULT_MODEL_REVISION)

    scope = None
    if args.path:
        scope = (brain_dir / args.path).resolve()
        if not scope.exists():
            sys.exit(f"BILBO: --path does not exist under BRAIN_PATH: {scope}")

    db_path = brain_dir / "index" / "bilbo.db"
    conn = open_db(db_path)

    if args.rebuild and not args.dry_run:
        conn.executescript("DELETE FROM chunks; DELETE FROM files; DELETE FROM meta;")
        conn.commit()
    else:
        check_model_consistency(conn, model_name, revision, args.rebuild)

    start = time.time()
    sync(conn, brain_dir, model_name, revision, scope, args.dry_run, args.rebuild)
    conn.close()
    print(f"BILBO: done in {time.time() - start:.1f}s. Index: {db_path}")


if __name__ == "__main__":
    main()
