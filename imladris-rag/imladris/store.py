"""SQLite index store: files, chunks with their vectors, and a key/value meta
table recording how the index was built (model, chunker, parameters)."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1"

SCHEMA = """
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


class IndexMismatch(Exception):
    """The index was built differently from what this run requests; mixing
    them would silently corrupt similarity search. Rebuild instead."""


def open_store(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def open_readonly(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)


def get_meta(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT key, value FROM meta").fetchall())


def set_meta(conn: sqlite3.Connection, **kwargs):
    conn.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        list(kwargs.items()),
    )
    conn.commit()


def reset(conn: sqlite3.Connection):
    conn.executescript("DELETE FROM chunks; DELETE FROM files; DELETE FROM meta;")
    conn.commit()


def check_consistency(conn: sqlite3.Connection, model_name: str, revision: str, chunker: str):
    """Raise IndexMismatch if the stored index was built with another model,
    revision, chunker or schema."""
    meta = get_meta(conn)
    if not meta.get("model_name"):
        return  # fresh store, nothing to compare
    if meta.get("chunker", "v1") != chunker:
        raise IndexMismatch(
            f"index was chunked with {meta.get('chunker', 'v1')}, this run requests {chunker}. "
            f"Run with --rebuild.")
    if meta.get("schema_version") and meta["schema_version"] != SCHEMA_VERSION:
        raise IndexMismatch(
            f"index schema changed ({meta['schema_version']} -> {SCHEMA_VERSION}). Run with --rebuild.")
    if meta["model_name"] != model_name or meta.get("model_revision") != revision:
        raise IndexMismatch(
            f"index was built with model={meta['model_name']}@{meta.get('model_revision')}, "
            f"but this run requests {model_name}@{revision}. Mixing vector spaces would "
            f"corrupt similarity search. Run with --rebuild to re-embed everything under "
            f"the new model, or keep the model the index was built with.")


def stored_hashes(conn: sqlite3.Connection) -> dict:
    return dict(conn.execute("SELECT path, content_hash FROM files").fetchall())


def replace_file(conn: sqlite3.Connection, path: str, content_hash: str, mtime: float,
                 indexed_at: str, rows: list[tuple[str, str, bytes, int]]):
    """Swap one file's chunks for `rows` = [(heading, text, vector_blob, token_count)]."""
    conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
    conn.executemany(
        "INSERT INTO chunks(path, ord, heading, text, vector, token_count) VALUES (?, ?, ?, ?, ?, ?)",
        [(path, i, heading, text, blob, tokens) for i, (heading, text, blob, tokens) in enumerate(rows)],
    )
    conn.execute(
        "INSERT INTO files(path, content_hash, mtime, chunk_count, indexed_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(path) DO UPDATE SET content_hash=excluded.content_hash, "
        "mtime=excluded.mtime, chunk_count=excluded.chunk_count, indexed_at=excluded.indexed_at",
        (path, content_hash, mtime, len(rows), indexed_at),
    )


def delete_file(conn: sqlite3.Connection, path: str):
    conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
    conn.execute("DELETE FROM files WHERE path = ?", (path,))
