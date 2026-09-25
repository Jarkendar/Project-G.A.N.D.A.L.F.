"""Qdrant index store: the whole schema-2 index in one collection.

Every node of the document tree is a point — `doc`, `section`, `block` —
with its fields as payload; blocks (and enriched docs) carry a named dense
vector "dense". A doc point also holds the document's record (hash, title,
frontmatter, privacy, supersession) and its outgoing links. Point 0 holds
the index meta. Node ids are integers handed out in write order, the same
way SQLite's AUTOINCREMENT does, so both stores number an index alike.
Vectors must come normalized (as the indexer writes them): the collection's
cosine space normalizes whatever it is given.

Keyword search: blocks also carry a sparse vector "bm25", computed by the
server (model "qdrant/bm25", IDF on the server side). Qdrant has no Polish
stemmer, so words are prepared here the way the SQLite store's FTS5 treats
them: lower-cased, diacritics dropped, cut to KEYWORD_STEM characters — on
both sides, so "polisie" and "polisa" meet as "polis". The server then only
splits on spaces: its stemmer and stopwords are off. The cut is fixed when a
collection is built and recorded in the meta.

Needs the `qdrant` extra (qdrant-client) and a running server — see
docker-compose.yml.
"""

import json
import re
import unicodedata
from urllib.parse import urlsplit

from qdrant_client import QdrantClient, models as m

from .store import SCHEMA_VERSION, Store

DENSE = "dense"
SPARSE = "bm25"
KEYWORD_STEM = 5
# avg_len is BM25's average document length in tokens. The server's default
# (256) assumes long documents; chunker v2 blocks average ~60 words (measured
# 2026-09-25 on the production index), and with 256 keyword hit@1 fell from
# .59 to .55. Lowercasing and folding are done by keyword_terms.
BM25_OPTIONS = {"stemmer": {"type": "none"}, "stopwords": {"languages": []}, "avg_len": 60,
                "lowercase": False, "ascii_folding": False}
META_ID = 0
SCROLL_PAGE = 512
# Filterable payload fields, indexed for fast filters.
KEYWORD_FIELDS = ("level", "path", "folder", "privacy", "superseded_by", "links[].dst")


def _match(key: str, value) -> m.FieldCondition:
    return m.FieldCondition(key=key, match=m.MatchValue(value=value))


def keyword_terms(words, stem: int) -> str:
    """Words as BM25 tokens: lower-cased, diacritics dropped, cut to `stem`
    characters (0 = whole words), space-separated."""
    out = []
    for word in words:
        word = word.lower().replace("ł", "l")
        word = "".join(ch for ch in unicodedata.normalize("NFKD", word) if not unicodedata.combining(ch))
        out.append(word[:stem] if stem else word)
    return " ".join(out)


def _bm25(words, stem: int) -> m.Document:
    return m.Document(text=keyword_terms(words, stem), model="qdrant/bm25", options=BM25_OPTIONS)


def _vector(blob: bytes | None) -> dict:
    import numpy as np
    return {DENSE: np.frombuffer(blob, dtype=np.float32).tolist()} if blob else {}


def _blob(point) -> bytes | None:
    import numpy as np
    vec = (point.vector or {}).get(DENSE)
    return np.asarray(vec, dtype=np.float32).tobytes() if vec else None


class QdrantStore(Store):
    """`url` is the server, `collection` the index; e.g. http://127.0.0.1:6333
    and "bilbo"."""

    def __init__(self, url: str, collection: str, readonly: bool = False):
        self.client = QdrantClient(url=url)
        self.collection, self.readonly = collection, readonly
        self.location = f"{url.rstrip('/')}/{collection}"
        self._meta = None
        self._next_id = None

    # --- helpers
    def _exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def _create(self, dim: int):
        self.client.create_collection(
            self.collection, vectors_config={DENSE: m.VectorParams(size=dim, distance=m.Distance.COSINE)},
            sparse_vectors_config={SPARSE: m.SparseVectorParams(modifier=m.Modifier.IDF)})
        for field in KEYWORD_FIELDS:
            self.client.create_payload_index(self.collection, field, m.PayloadSchemaType.KEYWORD)
        self.client.upsert(self.collection, wait=True,
                           points=[m.PointStruct(id=META_ID, vector={}, payload={
                               "level": "meta", "meta": {"keyword_stem": str(KEYWORD_STEM)}})])

    def _scroll(self, flt: m.Filter, payload=True, vectors=False) -> list:
        if not self._exists():
            return []
        out, offset = [], None
        while True:
            points, offset = self.client.scroll(self.collection, scroll_filter=flt, limit=SCROLL_PAGE,
                                                offset=offset, with_payload=payload, with_vectors=vectors)
            out.extend(points)
            if offset is None:
                return out  # scroll pages come in ascending id order

    def _allocate(self, n: int) -> int:
        """The first of `n` fresh node ids."""
        if self._next_id is None:
            meta = self.get_meta()
            self._next_id = int(meta.get("next_id", "1"))
        first, self._next_id = self._next_id, self._next_id + n
        return first

    # --- lifecycle and meta
    def close(self):
        self.client.close()

    def commit(self):
        if self._next_id is not None:
            self.set_meta(next_id=str(self._next_id))

    def get_meta(self) -> dict:
        if not self._exists():
            return {}
        points = self.client.retrieve(self.collection, [META_ID], with_payload=True)
        return dict(points[0].payload.get("meta", {})) if points else {}

    def set_meta(self, **kwargs):
        if not self._exists():
            raise RuntimeError(f"no collection {self.collection!r} yet — write a document first")
        meta = {**self.get_meta(), **{k: str(v) for k, v in kwargs.items()}}
        self.client.set_payload(self.collection, payload={"meta": meta}, points=[META_ID], wait=True)

    def reset(self):
        if self._exists():
            self.client.delete_collection(self.collection)
        self._next_id = None

    # --- writing
    def stored_hashes(self) -> dict:
        return {p.payload["path"]: p.payload["content_hash"]
                for p in self._scroll(m.Filter(must=[_match("level", "doc")]), payload=["path", "content_hash"])}

    def delete_document(self, path: str):
        if self._exists():
            self.client.delete(self.collection, wait=True, points_selector=m.FilterSelector(
                filter=m.Filter(must=[_match("path", path)])))

    def write_document(self, path: str, *, content_hash: str, mtime: float, indexed_at: str, title: str,
                       frontmatter: dict, privacy: str, sections: list[dict], blocks: list[dict],
                       links: list[dict], doc_text: str | None = None, doc_vector: bytes | None = None):
        if not self._exists():
            dim = len((doc_vector or next((b["vector"] for b in blocks if b.get("vector")), b""))) // 4
            if not dim:
                raise ValueError(f"cannot size a new collection from {path}: no vectors")
            self._create(dim)
        self.delete_document(path)
        superseded_by = frontmatter.get("superseded_by") or None
        common = {"path": path, "folder": path.split("/", 1)[0], "privacy": privacy,
                  "superseded_by": superseded_by}
        doc_id = self._allocate(1 + len(sections) + len(blocks))
        section_ids = list(range(doc_id + 1, doc_id + 1 + len(sections)))
        points = [m.PointStruct(id=doc_id, vector=_vector(doc_vector), payload={
            **common, "level": "doc", "parent_id": None, "ord": 0, "heading": title, "section_no": "",
            "line_start": None, "line_end": None, "text": doc_text or title, "token_count": None,
            "content_hash": content_hash, "mtime": mtime, "indexed_at": indexed_at, "title": title,
            "frontmatter": json.dumps(frontmatter, ensure_ascii=False), "block_count": len(blocks),
            "links": [{"dst": l["dst"], "raw": l["raw"], "kind": l["kind"], "line": l["line"]} for l in links]})]
        for i, sec in enumerate(sections):
            points.append(m.PointStruct(id=section_ids[i], vector={}, payload={
                **common, "level": "section", "parent_id": doc_id, "ord": i, "heading": sec["heading"],
                "section_no": sec["section_no"], "line_start": sec["line_start"], "line_end": sec["line_end"],
                "text": sec["text"], "token_count": None}))
        first_block = doc_id + 1 + len(sections)
        for i, b in enumerate(blocks):
            sec = b["section"]
            words = re.findall(r"\w+", f"{b['heading'] or ''} {b['text']}")
            vector = {**_vector(b["vector"]), SPARSE: _bm25(words, KEYWORD_STEM)}
            points.append(m.PointStruct(id=first_block + i, vector=vector, payload={
                **common, "level": "block", "parent_id": section_ids[sec] if sec is not None else doc_id,
                "ord": i, "heading": b["heading"], "section_no": sections[sec]["section_no"] if sec is not None else None,
                "line_start": b["line_start"], "line_end": b["line_end"], "text": b["text"],
                "token_count": b["token_count"]}))
        self.client.upsert(self.collection, points=points, wait=True)

    def relink(self, resolve) -> int:
        resolved = 0
        for p in self._scroll(m.Filter(must=[_match("level", "doc")]), payload=["path", "links"]):
            links = p.payload.get("links") or []
            new = [{**l, "dst": resolve(p.payload["path"], l["raw"], l["kind"])} for l in links]
            resolved += sum(1 for l in new if l["dst"] is not None)
            if new != links:
                self.client.set_payload(self.collection, payload={"links": new}, points=[p.id], wait=True)
        return resolved

    # --- reading
    def blocks(self) -> list[dict]:
        points = self._scroll(m.Filter(must=[_match("level", "block")]), vectors=[DENSE])
        return [{"id": p.id, "path": p.payload["path"], "ord": p.payload["ord"], "heading": p.payload["heading"],
                 "text": p.payload["text"], "vector": _blob(p), "section_no": p.payload["section_no"],
                 "line_start": p.payload["line_start"], "line_end": p.payload["line_end"]}
                for p in points if (p.vector or {}).get(DENSE)]

    def doc_vectors(self) -> list[tuple]:
        points = self._scroll(m.Filter(must=[_match("level", "doc")]), payload=["path"], vectors=[DENSE])
        return [(p.payload["path"], _blob(p)) for p in points if (p.vector or {}).get(DENSE)]

    def document(self, path: str) -> tuple:
        points = sorted(self._scroll(m.Filter(must=[_match("path", path)])),
                        key=lambda p: (p.payload["level"], p.payload["ord"]))
        doc = next(p for p in points if p.payload["level"] == "doc")
        sections = {p.id: (p.payload["section_no"], p.payload["heading"], p.payload["line_start"],
                           p.payload["line_end"], p.payload["text"])
                    for p in points if p.payload["level"] == "section"}
        blocks = [(p.id, p.payload["parent_id"], p.payload["text"], p.payload["line_start"], p.payload["line_end"])
                  for p in points if p.payload["level"] == "block"]
        return doc.payload["title"], doc.payload["privacy"], sections, blocks

    def neighbours(self, path: str) -> set[str]:
        out = set()
        for p in self._scroll(m.Filter(must=[_match("level", "doc"), _match("path", path)]), payload=["links"]):
            out |= {l["dst"] for l in p.payload.get("links") or [] if l["dst"]}
        linked_from = m.Filter(must=[_match("level", "doc"), _match("links[].dst", path)])
        out |= {p.payload["path"] for p in self._scroll(linked_from, payload=["path"])}
        return out - {path}

    def keyword_blocks(self, keywords: list[str], stem: int, top_k: int) -> list[tuple]:
        """BM25 over blocks. `stem` must equal the cut the collection was
        built with — unlike FTS5, it cannot change per query."""
        built = int(self.get_meta().get("keyword_stem", KEYWORD_STEM))
        if stem != built:
            raise ValueError(f"this Qdrant index cuts keywords to {built} characters; --stem {stem} "
                             f"would never match (rebuild the collection to change it)")
        if not keywords or not self._exists():
            return []
        points = self.client.query_points(self.collection, query=_bm25(dict.fromkeys(keywords), built),
                                          using=SPARSE, limit=top_k).points
        return [(p.id, p.score) for p in points]


def open_qdrant(location: str, readonly: bool = False) -> QdrantStore:
    """`location` = "<server url>/<collection>", e.g. http://127.0.0.1:6333/bilbo."""
    parts = urlsplit(location)
    base, _, collection = parts.path.rstrip("/").rpartition("/")
    if not collection:
        raise ValueError(f"no collection in {location!r}; expected <url>/<collection>")
    return QdrantStore(f"{parts.scheme}://{parts.netloc}{base}", collection, readonly=readonly)
