"""Index stores. `Store` is the contract every backend meets; `SqliteStore`
is the SQLite one (a single file, no server).

Schema 2 (hierarchical), whatever the backend:
  documents — one per file: hash, title, frontmatter, privacy, supersession
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
    text TEXT NOT NULL,                 -- block: chunk text; section: its body; doc: title or its enrichment text
    token_count INTEGER,
    vector BLOB                         -- float32, normalized; blocks, and docs when enriched
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


def fts_match(keywords: list[str], stem: int) -> str:
    """An FTS5 OR-query of `keywords`, each cut to `stem` characters and
    prefix-matched (0 = whole words)."""
    terms = []
    for kw in dict.fromkeys(keywords):
        kw = kw.replace('"', "")
        terms.append(f'"{kw[:stem]}"*' if stem and len(kw) > stem else f'"{kw}"')
    return " OR ".join(terms)


class Store:
    """What the indexer, search and context building need from an index.

    Rows handed out: `blocks()` -> dicts with id, path, ord, heading, text,
    vector (bytes), section_no, line_start, line_end, in id order;
    `doc_vectors()` -> (path, vector bytes) of documents that have one;
    `document(path)` -> (title, privacy, sections, blocks) where sections maps
    a section id to (section_no, heading, line_start, line_end, text) and
    blocks are (id, parent id, text, line_start, line_end) in file order."""

    location: str
    server_search = False  # True: nearest() runs the vector search in the store itself

    # --- lifecycle and meta
    def close(self): raise NotImplementedError
    def commit(self): raise NotImplementedError
    def get_meta(self) -> dict: raise NotImplementedError
    def set_meta(self, **kwargs): raise NotImplementedError
    def reset(self): raise NotImplementedError

    def check_consistency(self, model_name: str, revision: str, chunker: str):
        """Raise IndexMismatch if the stored index was built with another
        schema, model, revision or chunker."""
        meta = self.get_meta()
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

    # --- writing
    def stored_hashes(self) -> dict: raise NotImplementedError
    def delete_document(self, path: str): raise NotImplementedError

    def write_document(self, path: str, *, content_hash: str, mtime: float, indexed_at: str, title: str,
                       frontmatter: dict, privacy: str, sections: list[dict], blocks: list[dict],
                       links: list[dict], doc_text: str | None = None, doc_vector: bytes | None = None):
        """Replace one document. `sections`: dicts with heading, section_no,
        line_start, line_end, text. `blocks`: dicts with heading, section
        (index into `sections`, or None), line_start, line_end, text,
        token_count, vector (bytes). `links`: dicts with dst, raw, kind, line."""
        raise NotImplementedError

    def relink(self, resolve) -> int:
        """Re-resolve every stored link with `resolve(src, raw, kind)` -> dst
        or None; returns how many links resolve."""
        raise NotImplementedError

    # --- reading
    def blocks(self) -> list[dict]: raise NotImplementedError
    def doc_vectors(self) -> list[tuple]: raise NotImplementedError
    def document(self, path: str) -> tuple: raise NotImplementedError
    def neighbours(self, path: str) -> set[str]: raise NotImplementedError

    def keyword_blocks(self, keywords: list[str], stem: int, top_k: int) -> list[tuple]:
        """(block id, score) of the best keyword matches, best first."""
        raise NotImplementedError

    def nearest(self, vector, top_k: int, min_score: float) -> list[tuple]:
        """(block id, cosine score) of the blocks nearest to a normalized
        `vector`, best first, none below `min_score`. Only stores with
        `server_search`; the others are searched in memory by the caller."""
        raise NotImplementedError

    def export_documents(self):
        """Every document as write_document keyword arguments (path
        included), in node-id order — what copy_store replays."""
        raise NotImplementedError


class SqliteStore(Store):
    def __init__(self, db_path: Path, readonly: bool = False):
        self.db_path, self.location = db_path, str(db_path)
        if readonly:
            self.conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
            return
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        if self._has_table("chunks"):
            return  # a schema-1 index: leave it alone, check_consistency reports it
        self.conn.executescript(SCHEMA)
        self._ensure_fts()
        self.conn.commit()

    def _has_table(self, name: str) -> bool:
        return self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                 (name,)).fetchone() is not None

    def _ensure_fts(self):
        """Backfill blocks_fts from nodes when it is empty but blocks exist."""
        if self.conn.execute("SELECT 1 FROM blocks_fts LIMIT 1").fetchone():
            return
        self.conn.execute("INSERT INTO blocks_fts(rowid, heading, text) "
                          "SELECT id, heading, text FROM nodes WHERE level = 'block'")

    def close(self):
        self.conn.close()

    def commit(self):
        self.conn.commit()

    def get_meta(self) -> dict:
        if not self._has_table("meta"):
            return {}
        return dict(self.conn.execute("SELECT key, value FROM meta").fetchall())

    def set_meta(self, **kwargs):
        self.conn.executemany(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(kwargs.items()),
        )
        self.conn.commit()

    def reset(self):
        """Empty the store — and drop a schema-1 layout, so a rebuild upgrades it."""
        self.conn.executescript("""
            DROP TABLE IF EXISTS chunks; DROP TABLE IF EXISTS files;
            DROP TABLE IF EXISTS links; DROP TABLE IF EXISTS nodes;
            DROP TABLE IF EXISTS documents; DROP TABLE IF EXISTS meta;
            DROP TABLE IF EXISTS blocks_fts;
        """)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def stored_hashes(self) -> dict:
        if not self._has_table("documents"):
            return {}  # empty, or a schema-1 index (which only a rebuild replaces)
        return dict(self.conn.execute("SELECT path, content_hash FROM documents").fetchall())

    def delete_document(self, path: str):
        conn = self.conn
        conn.execute("DELETE FROM blocks_fts WHERE rowid IN "
                     "(SELECT id FROM nodes WHERE path = ? AND level = 'block')", (path,))
        conn.execute("DELETE FROM nodes WHERE path = ?", (path,))
        conn.execute("DELETE FROM links WHERE src = ?", (path,))
        conn.execute("DELETE FROM documents WHERE path = ?", (path,))

    def write_document(self, path: str, *, content_hash: str, mtime: float, indexed_at: str, title: str,
                       frontmatter: dict, privacy: str, sections: list[dict], blocks: list[dict],
                       links: list[dict], doc_text: str | None = None, doc_vector: bytes | None = None):
        conn = self.conn
        self.delete_document(path)
        conn.execute(
            "INSERT INTO documents(path, content_hash, mtime, indexed_at, title, frontmatter, privacy, "
            "superseded_by, block_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (path, content_hash, mtime, indexed_at, title, json.dumps(frontmatter, ensure_ascii=False),
             privacy, frontmatter.get("superseded_by") or None, len(blocks)),
        )
        doc_id = conn.execute(
            "INSERT INTO nodes(path, level, parent_id, ord, heading, section_no, line_start, line_end, text, "
            "vector) VALUES (?, 'doc', NULL, 0, ?, '', NULL, NULL, ?, ?)",
            (path, title, doc_text or title, doc_vector)).lastrowid
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

    def relink(self, resolve) -> int:
        rows = self.conn.execute("SELECT rowid, src, raw, kind FROM links").fetchall()
        for rowid, src, raw, kind in rows:
            self.conn.execute("UPDATE links SET dst = ? WHERE rowid = ?", (resolve(src, raw, kind), rowid))
        return self.conn.execute("SELECT COUNT(*) FROM links WHERE dst IS NOT NULL").fetchone()[0]

    def blocks(self) -> list[dict]:
        keys = ("path", "ord", "heading", "text", "vector", "section_no", "line_start", "line_end", "id")
        if self._has_table("nodes"):
            rows = self.conn.execute(
                "SELECT path, ord, heading, text, vector, section_no, line_start, line_end, id "
                "FROM nodes WHERE level = 'block' AND vector IS NOT NULL ORDER BY id").fetchall()
        else:  # schema 1: read-only compatibility until the index is rebuilt
            rows = [r + (None, None, None, None) for r in self.conn.execute(
                "SELECT path, ord, heading, text, vector FROM chunks ORDER BY id").fetchall()]
        return [dict(zip(keys, r)) for r in rows]

    def doc_vectors(self) -> list[tuple]:
        if not self._has_table("nodes"):
            return []
        return self.conn.execute("SELECT path, vector FROM nodes WHERE level = 'doc' AND vector IS NOT NULL "
                                 "ORDER BY id").fetchall()

    def document(self, path: str) -> tuple:
        title, privacy = self.conn.execute("SELECT title, privacy FROM documents WHERE path = ?",
                                           (path,)).fetchone()
        sections = {row[0]: row[1:] for row in self.conn.execute(
            "SELECT id, section_no, heading, line_start, line_end, text FROM nodes "
            "WHERE path = ? AND level = 'section' ORDER BY ord", (path,))}
        blocks = self.conn.execute(
            "SELECT id, parent_id, text, line_start, line_end FROM nodes "
            "WHERE path = ? AND level = 'block' ORDER BY ord", (path,)).fetchall()
        return title, privacy, sections, blocks

    def neighbours(self, path: str) -> set[str]:
        rows = self.conn.execute("SELECT dst FROM links WHERE src = ? AND dst IS NOT NULL "
                                 "UNION SELECT src FROM links WHERE dst = ?", (path, path)).fetchall()
        return {r[0] for r in rows} - {path}

    def export_documents(self):
        docs = self.conn.execute(
            "SELECT d.path, d.content_hash, d.mtime, d.indexed_at, d.title, d.frontmatter, d.privacy, "
            "n.id, n.text, n.vector FROM documents d JOIN nodes n ON n.path = d.path AND n.level = 'doc' "
            "ORDER BY n.id").fetchall()
        for path, content_hash, mtime, indexed_at, title, frontmatter, privacy, doc_id, doc_text, doc_vector in docs:
            section_rows = self.conn.execute(
                "SELECT id, heading, section_no, line_start, line_end, text FROM nodes "
                "WHERE path = ? AND level = 'section' ORDER BY ord", (path,)).fetchall()
            section_index = {row[0]: i for i, row in enumerate(section_rows)}
            blocks = [{"heading": heading, "section": section_index.get(parent), "line_start": start,
                       "line_end": end, "text": text, "token_count": tokens, "vector": vector}
                      for parent, heading, start, end, text, tokens, vector in self.conn.execute(
                          "SELECT parent_id, heading, line_start, line_end, text, token_count, vector FROM nodes "
                          "WHERE path = ? AND level = 'block' ORDER BY ord", (path,))]
            links = [{"dst": dst, "raw": raw, "kind": kind, "line": line} for dst, raw, kind, line in
                     self.conn.execute("SELECT dst, raw, kind, line FROM links WHERE src = ? ORDER BY rowid",
                                       (path,))]
            yield {"path": path, "content_hash": content_hash, "mtime": mtime, "indexed_at": indexed_at,
                   "title": title, "frontmatter": json.loads(frontmatter), "privacy": privacy,
                   "sections": [{"heading": h, "section_no": no, "line_start": a, "line_end": b, "text": t}
                                for _, h, no, a, b, t in section_rows],
                   "blocks": blocks, "links": links,
                   "doc_text": doc_text if doc_vector is not None else None, "doc_vector": doc_vector}

    def keyword_blocks(self, keywords: list[str], stem: int, top_k: int) -> list[tuple]:
        match = fts_match(keywords, stem)
        if not match or not self._has_table("nodes"):
            return []
        rows = self.conn.execute("SELECT rowid, bm25(blocks_fts) FROM blocks_fts WHERE blocks_fts MATCH ? "
                                 "ORDER BY bm25(blocks_fts) LIMIT ?", (match, top_k)).fetchall()
        return [(rowid, -rank) for rowid, rank in rows]


def copy_store(src: Store, dst: Store, log=print) -> int:
    """Copy an index between backends without re-embedding: documents in
    their original order, then the meta. Returns the number of documents."""
    n = 0
    for doc in src.export_documents():
        dst.write_document(**doc)
        n += 1
        if n % 50 == 0:
            log(f"copied {n} documents ...")
    meta = src.get_meta()
    if meta:
        dst.set_meta(**meta)
    dst.commit()
    return n


def is_url(location) -> bool:
    return str(location).startswith(("http://", "https://"))


def open_store(location, readonly: bool = False) -> Store:
    """The store at `location`: "<qdrant url>/<collection>" (needs the qdrant
    extra), or a path to a SQLite file."""
    if is_url(location):
        from .qdrant_store import open_qdrant
        return open_qdrant(str(location), readonly=readonly)
    return SqliteStore(Path(location), readonly=readonly)
