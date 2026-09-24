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
import json
import os
import re
import sqlite3
import subprocess
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

# Candidate models for the Index v2 bake-off (IMPLEMENTATION.md Step 9, phase
# B), selectable with --model <key>. Each is pinned to a Hub commit like the
# default. Prefixes are what the model was trained with: e5 needs "query: " /
# "passage: ", arctic only a query prefix, granite none. arctic ships its own
# modeling code (trust_remote_code) — pinned, so it is always the same code.
MODEL_REGISTRY = {
    "minilm": {"name": DEFAULT_MODEL_NAME, "revision": DEFAULT_MODEL_REVISION},
    "e5-small": {"name": "intfloat/multilingual-e5-small",
                 "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
                 "query_prefix": "query: ", "passage_prefix": "passage: "},
    "granite-97m": {"name": "ibm-granite/granite-embedding-97m-multilingual-r2",
                    "revision": "835ad14087e140460703cf0fae09f97d469d65c2"},
    "granite-311m": {"name": "ibm-granite/granite-embedding-311m-multilingual-r2",
                     "revision": "44399559930365213510b1ee2eb15ded83374f0e"},
    "arctic-m": {"name": "Snowflake/snowflake-arctic-embed-m-v2.0",
                 "revision": "95c2741480856aa9666782eb4afe11959938017f",
                 "query_prefix": "query: ", "trust_remote_code": True,
                 # its GTE code otherwise demands xformers (a GPU kernel library)
                 "config_kwargs": {"use_memory_efficient_attention": False,
                                   "unpad_inputs": False}},
}
# Long-window models accept 8K-32K tokens; chunks never get near that, and an
# uncapped window only costs memory on an outlier.
MAX_SEQ_CAP = 1024

# Corpus rules: exclude Smeagol's logs (not knowledge, and privacy-sensitive
# per SKILL.md), the index's own folder, and per-folder CLAUDE.md files (these
# are operating instructions for Claude Code, not retrievable knowledge).
EXCLUDED_DIR_PARTS = {"index"}
EXCLUDED_SUBPATHS = ("current/smeagol",)
EXCLUDED_FILENAMES = {"CLAUDE.md"}

SCHEMA_VERSION = "1"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
MAX_CHUNK_WORDS = 90  # chunker v1: keeps chunks well under MiniLM's ~128-token window

# Chunker v2 (Index v2, phase B): structural — paragraph, list and table
# blocks packed within one section, never split mid-block unless a single
# block is too long for the window. Budgets are counted with the model's own
# tokenizer and include the title + heading-path prefix.
CHUNK_TARGET_TOKENS = 256
CHUNK_MAX_TOKENS = 512
SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+|\n+")


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


def read_gandalf_env(project_dir: Path) -> dict:
    """KEY=VALUE pairs from .claude/gandalf.env, taken literally (no shell
    quoting), so a JSON value such as BILBO_CHUNK_PARAMS needs no escaping."""
    values = {}
    try:
        for line in (project_dir / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def brain_head(brain_dir: Path) -> str | None:
    """Current HEAD commit of the brain/ repo, or None if it is not a git repo."""
    try:
        return subprocess.run(
            ["git", "-C", str(brain_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


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


def split_sections(body: str) -> list[tuple[list[str], str]]:
    """Split body into (heading_path, section_text) — heading_path is the full
    stack of enclosing headings, e.g. ["Portfolio", "XTB"]. The document's
    first H1 is left out: it restates the title, which every chunk carries
    anyway."""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[list[str], list[str]]] = [([], [])]
    seen_heading = False
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            if not (level == 1 and not seen_heading):
                stack.append((level, m.group(2).strip()))
            seen_heading = True
            sections.append(([h for _, h in stack], []))
        else:
            sections[-1][1].append(line)
    return [(path, "\n".join(lines).strip()) for path, lines in sections
            if any(l.strip() for l in lines)]


def split_oversize(block: str, budget: int, count) -> list[str]:
    """Split one block that exceeds the window: a table by row groups with the
    header repeated, anything else by sentences. A single sentence still over
    budget is cut by tokens as a last resort."""
    lines = block.splitlines()
    if len(lines) > 2 and all(l.lstrip().startswith("|") for l in lines):
        header, rows = lines[:2], lines[2:]
        pieces, current = [], []
        for row in rows:
            if current and count("\n".join(header + current + [row])) > budget:
                pieces.append("\n".join(header + current))
                current = []
            current.append(row)
        if current:
            pieces.append("\n".join(header + current))
        return pieces
    pieces, current = [], ""
    for sentence in (x for x in SENTENCE_END_RE.split(block) if x.strip()):
        candidate = f"{current} {sentence}".strip()
        if current and count(candidate) > budget:
            pieces.append(current)
            candidate = sentence
        current = candidate
    if current:
        pieces.append(current)
    out = []
    for piece in pieces:
        if count(piece) <= budget:
            out.append(piece)
            continue
        words = piece.split()  # last resort for a sentence with no breaks
        step = max(1, len(words) * budget // count(piece))
        out.extend(" ".join(words[i:i + step]) for i in range(0, len(words), step))
    return out


DEFAULT_CHUNK_PARAMS = {
    "prefix": "title+path",  # context embedded with each chunk: title+path | path | title | none
    "target": CHUNK_TARGET_TOKENS,  # pack blocks of one section up to this many tokens
    "merge_tiny": 0,         # fold chunks whose body is under this many tokens into a neighbour
    "skip_lines": "",        # regex; matching lines (boilerplate) are dropped before chunking
}


def chunk_markdown_v2(rel_path: Path, text: str, count, params: dict | None = None) -> list[tuple[str, str]]:
    """Return [(heading_path, text_to_embed), ...]. `count` returns a token
    count under the model being indexed; `params` overrides
    DEFAULT_CHUNK_PARAMS (the knobs the phase-B chunking ablation turns)."""
    params = {**DEFAULT_CHUNK_PARAMS, **(params or {})}
    fm, body = split_frontmatter(text)
    title = fm.get("title") or rel_path.stem
    if params["skip_lines"]:
        skip = re.compile(params["skip_lines"])
        body = "\n".join(l for l in body.splitlines() if not skip.search(l))

    def prefix_for(heading: str) -> str:
        mode = params["prefix"]
        if mode == "none":
            return ""
        if mode == "title" or not heading:
            return f"{title}\n\n" if mode != "path" or not heading else f"{heading}\n\n"
        if mode == "path":
            return f"{heading}\n\n"
        return f"{title}\n{heading}\n\n"

    pieces: list[tuple[str, str]] = []  # (heading, body) before prefixing
    for path, section_text in split_sections(body) or [([], body.strip())]:
        heading = " > ".join(h for h in path if h != title)
        prefix_tokens = count(prefix_for(heading))
        target = max(32, params["target"] - prefix_tokens)
        limit = max(32, CHUNK_MAX_TOKENS - prefix_tokens)

        blocks = []
        for block in (b.strip() for b in re.split(r"\n\s*\n", section_text)):
            if not block:
                continue
            blocks.extend([block] if count(block) <= limit else split_oversize(block, limit, count))

        current: list[str] = []
        for block in blocks:
            if current and count("\n\n".join(current + [block])) > target:
                pieces.append((heading, "\n\n".join(current)))
                current = []
            current.append(block)
        if current:
            pieces.append((heading, "\n\n".join(current)))

    if params["merge_tiny"]:
        merged: list[tuple[str, str]] = []
        carry: tuple[str, str] | None = None  # a tiny piece waiting for a following neighbour
        for heading, text_ in pieces:
            if carry:
                heading = " | ".join(h for h in (carry[0], heading) if h)
                text_ = f"{carry[1]}\n\n{text_}"
                carry = None
            if count(text_) >= params["merge_tiny"]:
                merged.append((heading, text_))
            elif merged and count(merged[-1][1] + text_) <= CHUNK_MAX_TOKENS:
                prev_heading, prev_text = merged.pop()
                label = " | ".join(dict.fromkeys(h for h in (prev_heading, heading) if h))
                merged.append((label, f"{prev_text}\n\n{text_}"))
            else:
                carry = (heading, text_)
        if carry:
            merged.append(carry)
        pieces = merged

    return [(heading or title, prefix_for(heading) + text_) for heading, text_ in pieces]


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


def check_model_consistency(conn: sqlite3.Connection, model_name: str, revision: str,
                            chunker: str, rebuild: bool):
    meta = get_meta(conn)
    if not meta.get("model_name"):
        return  # fresh DB, nothing to check yet
    if meta.get("chunker", "v1") != chunker and not rebuild:
        sys.exit(
            f"BILBO: index was chunked with {meta.get('chunker', 'v1')}, this run "
            f"requests {chunker}. Run with --rebuild."
        )
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

def sync(conn: sqlite3.Connection, brain_dir: Path, spec: dict, chunker: str,
         scope: Path | None, dry_run: bool, rebuild: bool, chunk_params: dict | None = None):
    model_name, revision = spec["name"], spec["revision"]
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
        import torch
        # float32 explicitly: transformers 5 keeps a checkpoint's saved dtype,
        # and bf16 weights (granite) fall back to a ~150x slower matmul on the
        # Pi 5's Cortex-A76, which has no bf16 support.
        model = SentenceTransformer(model_name, revision=revision,
                                    trust_remote_code=spec.get("trust_remote_code", False),
                                    model_kwargs={"dtype": torch.float32},
                                    config_kwargs=spec.get("config_kwargs"))
        model.max_seq_length = min(model.max_seq_length or MAX_SEQ_CAP, MAX_SEQ_CAP)
        tokenizer = model.tokenizer

        def count(text: str) -> int:
            return len(tokenizer(text, add_special_tokens=False)["input_ids"])

        per_file_chunks: dict[str, list[tuple[str, str]]] = {}
        all_texts: list[str] = []
        for rel in to_update:
            abs_path = brain_dir / rel
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_markdown_v2(rel, text, count, chunk_params) if chunker == "v2" else chunk_markdown(rel, text)
            per_file_chunks[rel.as_posix()] = chunks
            all_texts.extend(text for _, text in chunks)

        vectors = []
        if all_texts:
            print(f"BILBO: embedding {len(all_texts)} chunks from {len(to_update)} file(s) ...")
            passage_prefix = spec.get("passage_prefix", "")
            vectors = model.encode(
                [passage_prefix + t for t in all_texts], batch_size=16 if chunker == "v2" else 32,
                normalize_embeddings=True, show_progress_bar=True
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
                    (posix, i, heading, text, vector_to_blob(vec),
                     count(text) if chunker == "v2" else len(text.split())),
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
            embed_dim=str(model.get_sentence_embedding_dimension()),
            schema_version=SCHEMA_VERSION,
            chunker=chunker,
            query_prefix=spec.get("query_prefix", ""),
            trust_remote_code="1" if spec.get("trust_remote_code") else "0",
            config_kwargs=json.dumps(spec.get("config_kwargs") or {}),
            chunk_params=json.dumps({**DEFAULT_CHUNK_PARAMS, **(chunk_params or {})}
                                    if chunker == "v2" else {}, sort_keys=True),
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
    parser.add_argument("--model", type=str, default=None,
                        help="embedding model: a key of MODEL_REGISTRY (" + ", ".join(MODEL_REGISTRY) +
                             ") or a Hub name (revision then from BILBO_EMBED_REVISION)")
    parser.add_argument("--chunk-params", type=str, default=None,
                        help="chunker v2 only: JSON overriding DEFAULT_CHUNK_PARAMS, e.g. "
                             "'{\"prefix\": \"path\", \"merge_tiny\": 40}'")
    parser.add_argument("--chunker", choices=["v1", "v2"], default=None,
                        help="v1: heading + ~90-word windows (production); "
                             "v2: structural blocks within token budgets (Index v2)")
    parser.add_argument("--dry-run", action="store_true", help="report deltas without embedding or writing")
    parser.add_argument("--if-new-commits", action="store_true",
                        help="skip the run when brain/ HEAD equals the last indexed commit "
                             "(used by the post-commit/post-merge hooks in brain/)")
    parser.add_argument("--db", type=str, default=None,
                        help="write to this index instead of brain/index/bilbo.db — "
                             "for experimental variants compared by the Samwise eval")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parents[3]
    brain_dir = resolve_brain_path(project_dir)

    # Precedence: CLI flag > environment variable > .claude/gandalf.env > built-in
    # default. gandalf.env is what the post-commit hook runs with, so it is where
    # the production model and chunker are configured.
    genv = read_gandalf_env(project_dir)
    setting = lambda key, default=None: os.environ.get(key) or genv.get(key) or default
    args.chunker = args.chunker or setting("BILBO_CHUNKER", "v1")
    args.chunk_params = args.chunk_params or setting("BILBO_CHUNK_PARAMS")
    model_arg = args.model or setting("BILBO_EMBED_MODEL", "minilm")
    spec = MODEL_REGISTRY.get(model_arg) or next(
        (m for m in MODEL_REGISTRY.values() if m["name"] == model_arg), None)
    if spec is None:
        spec = {"name": model_arg}
    spec = {**spec, "revision": os.environ.get("BILBO_EMBED_REVISION", spec.get("revision", "main"))}
    model_name, revision = spec["name"], spec["revision"]

    scope = None
    if args.path:
        scope = (brain_dir / args.path).resolve()
        if not scope.exists():
            sys.exit(f"BILBO: --path does not exist under BRAIN_PATH: {scope}")

    db_path = Path(args.db).resolve() if args.db else brain_dir / "index" / "bilbo.db"
    conn = open_db(db_path)

    # Read HEAD before scanning: a commit landing mid-run then shows up as
    # "new" on the next check instead of being marked indexed unseen.
    head = brain_head(brain_dir)
    if args.if_new_commits and head and head == get_meta(conn).get("last_indexed_commit"):
        print(f"BILBO: brain/ HEAD {head[:7]} already indexed — nothing to do.")
        conn.close()
        return

    if args.rebuild and not args.dry_run:
        conn.executescript("DELETE FROM chunks; DELETE FROM files; DELETE FROM meta;")
        conn.commit()
    else:
        check_model_consistency(conn, model_name, revision, args.chunker, args.rebuild)

    start = time.time()
    chunk_params = json.loads(args.chunk_params) if args.chunk_params else None
    if chunk_params and set(chunk_params) - set(DEFAULT_CHUNK_PARAMS):
        sys.exit(f"BILBO: unknown --chunk-params keys: {set(chunk_params) - set(DEFAULT_CHUNK_PARAMS)}")
    sync(conn, brain_dir, spec, args.chunker, scope, args.dry_run, args.rebuild, chunk_params)
    # Only a full-scope run covers everything HEAD contains; a --path run
    # leaves the rest unchecked, so it must not claim the commit.
    if head and scope is None and not args.dry_run:
        set_meta(conn, last_indexed_commit=head)
    conn.close()
    print(f"BILBO: done in {time.time() - start:.1f}s. Index: {db_path}")


if __name__ == "__main__":
    main()
