"""SQLite index store.

Schema 2 (hierarchical):
  documents — one row per file: hash, title, frontmatter, privacy, supersession
  nodes     — the tree of each document: one `doc` node, its `section` nodes
              (heading path, number such as "2.3", line range, body text) and
              the `block` nodes under them — the embedded chunks
  links     — document-to-document links (markdown, wikilink, path mention)
  meta      — how the index was built (model, chunker, parameters)
"""

import json
import sqlite3
from pathlib import Path

SCHEMA_VERSION = "2"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    mtime REAL NOT NULL,
    indexed_at TEXT NOT NULL,
    title TEXT NOT NULL,
    frontmatter TEXT NOT NULL,          -- JSON object
    privacy TEXT NOT NULL,              -- "private" | "public", after the corpus' rules
    superseded_by TEXT,
    block_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('doc', 'section', 'block')),
    parent_id INTEGER REFERENCES nodes(id),
    ord INTEGER NOT NULL,               -- position among nodes of the same level in the file
    heading TEXT,                       -- display heading ("A > B"; a block's may join "A | B")
    section_no TEXT,                    -- "2.3"; "" for a preamble
    line_start INTEGER,
    line_end INTEGER,
    text TEXT NOT NULL,                 -- block: the embedded text; section: its body; doc: title
    token_count INTEGER,
    vector BLOB                         -- float32, normalized; blocks only for now
);
CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_level ON nodes(level);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(parent_id);
CREATE TABLE IF NOT EXISTS links (
    src TEXT NOT NULL,
    dst TEXT,                           -- corpus-relative path, NULL if unresolved
    raw TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- markdown | wikilink | path
    line INTEGER
);
CREATE INDEX IF NOT EXISTS idx_links_src ON links(src);
CREATE INDEX IF NOT EXISTS idx_links_dst ON links(dst);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Full-text index over blocks (rowid = nodes.id). Additive: an index built
-- before it existed is backfilled from `nodes` by ensure_fts, no re-embedding.
CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(
    heading, text, tokenize = 'unicode61 remove_diacritics 2'
);
"""


class IndexMismatch(Exception):
    """The index was built differently from what this run requests; mixing
    them would silently corrupt similarity search. Rebuild instead."""


def open_store(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    if _has_table(conn, "chunks"):
        return conn  # a schema-1 index: leave it alone, check_consistency reports it
    conn.executescript(SCHEMA)
    ensure_fts(conn)
    conn.commit()
    return conn


def ensure_fts(conn: sqlite3.Connection):
    """Backfill blocks_fts from nodes when it is empty but blocks exist."""
    if conn.execute("SELECT 1 FROM blocks_fts LIMIT 1").fetchone():
        return
    conn.execute("INSERT INTO blocks_fts(rowid, heading, text) "
                 "SELECT id, heading, text FROM nodes WHERE level = 'block'")


def open_readonly(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def get_meta(conn: sqlite3.Connection) -> dict:
    if not _has_table(conn, "meta"):
        return {}
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def set_meta(conn: sqlite3.Connection, **kwargs):
    conn.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(kwargs.items()),
    )
    conn.commit()


def reset(conn: sqlite3.Connection):
    """Empty the store — and drop a schema-1 layout, so a rebuild upgrades it."""
    conn.executescript("""
        DROP TABLE IF EXISTS chunks; DROP TABLE IF EXISTS files;
        DROP TABLE IF EXISTS links; DROP TABLE IF EXISTS nodes;
        DROP TABLE IF EXISTS documents; DROP TABLE IF EXISTS meta;
        DROP TABLE IF EXISTS blocks_fts;
    """)
    conn.executescript(SCHEMA)
    conn.commit()


def check_consistency(conn: sqlite3.Connection, model_name: str, revision: str, chunker: str):
    """Raise IndexMismatch if the stored index was built with another schema,
    model, revision or chunker."""
    meta = get_meta(conn)
    if not meta.get("model_name"):
        return  # fresh store, nothing to compare
    if meta.get("schema_version", "1") != SCHEMA_VERSION:
        raise IndexMismatch(
            f"index schema is {meta.get('schema_version', '1')}, this engine writes "
            f"{SCHEMA_VERSION}. Run with --rebuild.")
    if meta.get("chunker", "v1") != chunker:
        raise IndexMismatch(
            f"index was chunked with {meta.get('chunker', 'v1')}, this run requests {chunker}. "
            f"Run with --rebuild.")
    if meta["model_name"] != model_name or meta.get("model_revision") != revision:
        raise IndexMismatch(
            f"index was built with model={meta['model_name']}@{meta.get('model_revision')}, "
            f"but this run requests {model_name}@{revision}. Mixing vector spaces would "
            f"corrupt similarity search. Run with --rebuild to re-embed everything under "
            f"the new model, or keep the model the index was built with.")


def stored_hashes(conn: sqlite3.Connection) -> dict:
    if not _has_table(conn, "documents"):
        return {}  # empty, or a schema-1 index (which only a rebuild replaces)
    return dict(conn.execute("SELECT path, content_hash FROM documents").fetchall())


def delete_document(conn: sqlite3.Connection, path: str):
    conn.execute("DELETE FROM blocks_fts WHERE rowid IN "
                 "(SELECT id FROM nodes WHERE path = ? AND level = 'block')", (path,))
    conn.execute("DELETE FROM nodes WHERE path = ?", (path,))
    conn.execute("DELETE FROM links WHERE src = ?", (path,))
    conn.execute("DELETE FROM documents WHERE path = ?", (path,))


def write_document(conn: sqlite3.Connection, path: str, *, content_hash: str, mtime: float,
                   indexed_at: str, title: str, frontmatter: dict, privacy: str,
                   sections: list[dict], blocks: list[dict], links: list[dict]):
    """Replace one document's rows. `sections`: dicts with heading, section_no,
    line_start, line_end, text. `blocks`: dicts with heading, section (index
    into `sections`, or None), line_start, line_end, text, token_count,
    vector (bytes). `links`: dicts with dst, raw, kind, line."""
    delete_document(conn, path)
    conn.execute(
        "INSERT INTO documents(path, content_hash, mtime, indexed_at, title, frontmatter, privacy, "
        "superseded_by, block_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (path, content_hash, mtime, indexed_at, title, json.dumps(frontmatter, ensure_ascii=False),
         privacy, frontmatter.get("superseded_by") or None, len(blocks)),
    )
    doc_id = conn.execute(
        "INSERT INTO nodes(path, level, parent_id, ord, heading, section_no, line_start, line_end, text) "
        "VALUES (?, 'doc', NULL, 0, ?, '', NULL, NULL, ?)", (path, title, title)).lastrowid
    section_ids = []
    for i, sec in enumerate(sections):
        section_ids.append(conn.execute(
            "INSERT INTO nodes(path, level, parent_id, ord, heading, section_no, line_start, line_end, text) "
            "VALUES (?, 'section', ?, ?, ?, ?, ?, ?, ?)",
            (path, doc_id, i, sec["heading"], sec["section_no"], sec["line_start"], sec["line_end"],
             sec["text"])).lastrowid)
    conn.executemany(
        "INSERT INTO nodes(path, level, parent_id, ord, heading, section_no, line_start, line_end, text, "
        "token_count, vector) VALUES (?, 'block', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(path, section_ids[b["section"]] if b["section"] is not None else doc_id, i, b["heading"],
          sections[b["section"]]["section_no"] if b["section"] is not None else None,
          b["line_start"], b["line_end"], b["text"], b["token_count"], b["vector"])
         for i, b in enumerate(blocks)],
    )
    conn.execute("INSERT INTO blocks_fts(rowid, heading, text) "
                 "SELECT id, heading, text FROM nodes WHERE path = ? AND level = 'block'", (path,))
    conn.executemany("INSERT INTO links(src, dst, raw, kind, line) VALUES (?, ?, ?, ?, ?)",
                     [(path, l["dst"], l["raw"], l["kind"], l["line"]) for l in links])
