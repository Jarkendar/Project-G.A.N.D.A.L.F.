"""Index stores. `Store` is the contract every backend meets; the one
backend is Qdrant (`qdrant_store.QdrantStore`). A SQLite store served until
Qdrant matched it on the golden set, and was removed on 2026-09-26.

Schema 2 (hierarchical), whatever the backend:
  documents — one per file: hash, title, frontmatter, privacy, supersession
  nodes     — the tree of each document: one `doc` node, its `section` nodes
              (heading path, number such as "2.3", line range, body text) and
              the `block` nodes under them — the embedded chunks
  links     — document-to-document links (markdown, wikilink, path mention)
  meta      — how the index was built (model, chunker, parameters)
"""

SCHEMA_VERSION = "2"



class IndexMismatch(Exception):
    """The index was built differently from what this run requests; mixing
    them would silently corrupt similarity search. Rebuild instead."""


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


def is_url(location) -> bool:
    return str(location).startswith(("http://", "https://"))


def open_store(location, readonly: bool = False) -> Store:
    """The store at `location`: "<qdrant url>/<collection>"."""
    if not is_url(location):
        raise ValueError(f"not an index location: {location!r} — expected <qdrant url>/<collection>, "
                         f"e.g. http://127.0.0.1:6333/bilbo")
    from .qdrant_store import open_qdrant
    return open_qdrant(str(location), readonly=readonly)
