"""Query-time retrieval over an index built by `indexer.sync`.

semantic — encode the query the way the index was built (model, revision,
           query prefix, config overrides from `meta`) and rank chunks by
           cosine similarity (vectors are normalized, so a dot product).
keyword  — baseline: rank whole files by keyword hit count.
hybrid   — Reciprocal Rank Fusion of semantic and keyword (file level).
fts      — BM25 over blocks (SQLite FTS5); query words are cut to a stem
           prefix, a cheap stand-in for stemming inflected languages.
hybrid_fts — Reciprocal Rank Fusion of semantic and fts, both block level.
diversify — keep only the best block of each file.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import store
from .corpus import Corpus
from .models import ModelSpec, load_model

RRF_K = 60  # standard Reciprocal Rank Fusion constant
# Keyword paths (keyword_search, fts_*) take a `stopwords` set from the caller:
# which words carry no meaning depends on the corpus' languages, so the engine
# ships none. load_stopwords reads a plain one-word-per-line file.
SNIPPET_CHARS = 240



class IndexUnavailable(Exception):
    """No usable index at the given path (missing, empty, or without meta)."""


@dataclass
class Index:
    """Loaded, read-only view of an index."""
    db_path: Path
    spec: ModelSpec
    embed_dim: int
    ids: list = field(default_factory=list)          # nodes.id per chunk (schema 2), else None
    paths: list[str] = field(default_factory=list)
    ords: list[int] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    section_nos: list = field(default_factory=list)  # "2.3" per chunk; None on schema-1 indexes
    line_ranges: list = field(default_factory=list)  # (start, end) per chunk, or (None, None)
    vectors: np.ndarray = None  # (n_chunks, embed_dim), float32, normalized
    doc_paths: list = field(default_factory=list)  # documents with an enrichment vector
    doc_vectors: np.ndarray = None                 # (n_docs, embed_dim), or None


def load_index(db_path: Path) -> Index:
    if not db_path.is_file():
        raise IndexUnavailable(f"no index at {db_path}")
    conn = store.open_readonly(db_path)
    try:
        meta = store.get_meta(conn)
        if not meta.get("model_name"):
            raise IndexUnavailable(f"index at {db_path} has no meta")
        if store._has_table(conn, "nodes"):
            rows = conn.execute(
                "SELECT path, ord, heading, text, vector, section_no, line_start, line_end, id "
                "FROM nodes WHERE level = 'block' AND vector IS NOT NULL ORDER BY id").fetchall()
            docs = conn.execute("SELECT path, vector FROM nodes WHERE level = 'doc' AND vector IS NOT NULL "
                                "ORDER BY id").fetchall()
        else:  # schema 1: read-only compatibility until the index is rebuilt
            docs = []
            rows = [r + (None, None, None, None) for r in conn.execute(
                "SELECT path, ord, heading, text, vector FROM chunks ORDER BY id").fetchall()]
    finally:
        conn.close()
    if not rows:
        raise IndexUnavailable(f"index at {db_path} has no chunks")

    spec = ModelSpec(
        name=meta["model_name"],
        revision=meta.get("model_revision", "main"),
        query_prefix=meta.get("query_prefix", ""),
        trust_remote_code=meta.get("trust_remote_code") == "1",
        config_kwargs=json.loads(meta.get("config_kwargs") or "{}"),
    )
    return Index(
        db_path=db_path,
        spec=spec,
        embed_dim=int(meta.get("embed_dim", "0")),
        ids=[r[8] for r in rows],
        paths=[r[0] for r in rows],
        ords=[r[1] for r in rows],
        headings=[r[2] or "" for r in rows],
        texts=[r[3] for r in rows],
        section_nos=[r[5] for r in rows],
        line_ranges=[(r[6], r[7]) for r in rows],
        vectors=np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows]),
        doc_paths=[d[0] for d in docs],
        doc_vectors=np.stack([np.frombuffer(d[1], dtype=np.float32) for d in docs]) if docs else None,
    )


def embed_query(idx: Index, query: str) -> np.ndarray:
    model = load_model(idx.spec)
    return model.encode([idx.spec.query_prefix + query], normalize_embeddings=True)[0].astype(np.float32)


def make_snippet(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= SNIPPET_CHARS:
        return collapsed
    return collapsed[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


def semantic_search(idx: Index, query: str, top_k: int, min_score: float) -> list[dict]:
    if idx.vectors.shape[0] == 0:
        return []
    scores = idx.vectors @ embed_query(idx, query)
    results = []
    for i in np.argsort(-scores):
        score = float(scores[i])
        if score < min_score:
            break  # descending order: nothing further clears the bar
        results.append({
            "score": round(score, 4),
            "path": idx.paths[i],
            "heading": idx.headings[i],
            "ord": idx.ords[i],
            "snippet": make_snippet(idx.texts[i]),
            "section_no": idx.section_nos[i],
            "lines": list(idx.line_ranges[i]) if idx.line_ranges[i][0] is not None else None,
            "chunk": int(i),  # position in idx.texts, for callers that need the full text
        })
        if len(results) >= top_k:
            break
    return results


def load_stopwords(path: Path) -> frozenset:
    """One word per line; blank lines and "#" comments ignored; lower-cased."""
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            words.add(line)
    return frozenset(words)


def keywords_from_query(query: str, stopwords: frozenset = frozenset()) -> list[str]:
    # Case-preserving pass first so all-caps acronyms (CV, AI, US) survive at
    # 2 characters, while genuine 2-letter stopwords (o, w, z, do...) drop.
    keywords = []
    for t in re.findall(r"\w+", query):
        low = t.lower()
        if low in stopwords:
            continue
        if len(t) >= 3 or (t.isupper() and len(t) >= 2):
            keywords.append(low)
    return keywords


def keyword_search(corpus: Corpus, query: str, top_k: int,
                   stopwords: frozenset = frozenset()) -> list[dict]:
    keywords = keywords_from_query(query, stopwords)
    if not keywords:
        return []
    results = []
    for rel in corpus.discover():
        try:
            text = (corpus.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lower = text.lower()
        count = sum(lower.count(kw) for kw in keywords)
        if count == 0:
            continue
        snippet = next(
            (line.strip() for line in text.splitlines()
             if any(kw in line.lower() for kw in keywords) and line.strip()),
            text.strip().splitlines()[0] if text.strip() else "",
        )
        results.append({"score": count, "path": rel.as_posix(), "heading": None,
                        "ord": None, "snippet": make_snippet(snippet)})
    results.sort(key=lambda r: -r["score"])
    return results[:top_k]


def _best_per_path(results: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for r in results:
        best.setdefault(r["path"], r)
    return list(best.values())


def hybrid_search(idx: Index, corpus: Corpus, query: str, top_k: int,
                  stopwords: frozenset = frozenset()) -> list[dict]:
    pool = max(top_k * 5, 40)
    semantic_hits = _best_per_path(semantic_search(idx, query, top_k=pool, min_score=-1.0))
    keyword_hits = keyword_search(corpus, query, top_k=pool, stopwords=stopwords)

    rrf: dict[str, float] = {}
    by_path: dict[str, dict] = {}
    for hits in (semantic_hits, keyword_hits):
        for rank, r in enumerate(hits):
            rrf[r["path"]] = rrf.get(r["path"], 0.0) + 1.0 / (RRF_K + rank + 1)
            by_path.setdefault(r["path"], r)

    fused = [{"score": round(score, 6), "path": path,
              "heading": by_path[path].get("heading"), "ord": by_path[path].get("ord"),
              "snippet": by_path[path].get("snippet"), "chunk": by_path[path].get("chunk"),
              "section_no": by_path[path].get("section_no"), "lines": by_path[path].get("lines")}
             for path, score in rrf.items()]
    fused.sort(key=lambda r: -r["score"])
    return fused[:top_k]


# --- full text (FTS5) ----------------------------------------------------------

def _hit(idx: Index, i: int, score: float) -> dict:
    return {"score": round(score, 4), "path": idx.paths[i], "heading": idx.headings[i],
            "ord": idx.ords[i], "snippet": make_snippet(idx.texts[i]),
            "section_no": idx.section_nos[i],
            "lines": list(idx.line_ranges[i]) if idx.line_ranges[i][0] is not None else None,
            "chunk": int(i)}


def fts_query(query: str, stem: int, stopwords: frozenset = frozenset()) -> str:
    """An FTS5 OR-query of the query's keywords, each cut to `stem` characters
    and prefix-matched (0 = whole words)."""
    terms = []
    for kw in dict.fromkeys(keywords_from_query(query, stopwords)):
        kw = kw.replace('"', "")
        terms.append(f'"{kw[:stem]}"*' if stem and len(kw) > stem else f'"{kw}"')
    return " OR ".join(terms)


def fts_search(idx: Index, query: str, top_k: int, stem: int = 5,
               stopwords: frozenset = frozenset()) -> list[dict]:
    """BM25-ranked blocks. Empty on a schema-1 index or without keywords."""
    match = fts_query(query, stem, stopwords)
    if not match or idx.ids[0] is None:
        return []
    positions = {node_id: i for i, node_id in enumerate(idx.ids)}
    conn = store.open_readonly(idx.db_path)
    try:
        rows = conn.execute("SELECT rowid, bm25(blocks_fts) FROM blocks_fts WHERE blocks_fts MATCH ? "
                            "ORDER BY bm25(blocks_fts) LIMIT ?", (match, top_k)).fetchall()
    finally:
        conn.close()
    return [_hit(idx, positions[rowid], -rank) for rowid, rank in rows if rowid in positions]


def hybrid_fts_search(idx: Index, query: str, top_k: int, stem: int = 5,
                      fts_weight: float = 1.0, stopwords: frozenset = frozenset()) -> list[dict]:
    """Reciprocal Rank Fusion of semantic and FTS rankings, block by block;
    `fts_weight` scales the FTS side (1.0 = plain RRF)."""
    pool = max(top_k * 5, 40)
    rrf: dict[int, float] = {}
    for weight, hits in ((1.0, semantic_search(idx, query, top_k=pool, min_score=-1.0)),
                         (fts_weight, fts_search(idx, query, top_k=pool, stem=stem, stopwords=stopwords))):
        for rank, hit in enumerate(hits):
            rrf[hit["chunk"]] = rrf.get(hit["chunk"], 0.0) + weight / (RRF_K + rank + 1)
    fused = sorted(rrf.items(), key=lambda kv: -kv[1])[:top_k]
    return [_hit(idx, i, score) for i, score in fused]


def diversify(results: list[dict], top_k: int) -> list[dict]:
    """The best-ranked block of each file, in order — so a multi-file question
    is not answered by five blocks of one file."""
    return _best_per_path(results)[:top_k]
