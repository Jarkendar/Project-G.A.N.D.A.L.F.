"""Query-time retrieval over an index built by `indexer.sync`.

semantic — encode the query the way the index was built (model, revision,
           query prefix, config overrides from `meta`) and rank chunks by
           cosine similarity (vectors are normalized, so a dot product).
keyword  — baseline: rank whole files by keyword hit count.
hybrid   — Reciprocal Rank Fusion of the two.
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
SNIPPET_CHARS = 240

STOPWORDS = {
    # English function words / query-pattern filler ("what do I know about...")
    "the", "and", "for", "with", "this", "that", "from", "have", "what",
    "about", "your", "how", "when", "where", "which", "does", "did", "was",
    "were", "are", "into", "over", "under", "who", "whom", "will", "can",
    "know", "tell", "find", "show", "any",
    # Polish function words / query-pattern filler ("co wiem o... / jakie mam...")
    "wiem", "jak", "jakie", "jakich", "jaki", "jaka", "czy", "się", "nie",
    "dla", "tego", "tym", "oraz", "moje", "moja", "mój", "moim", "jest",
    "były", "była", "był", "coś", "tam", "tutaj", "znam", "znaj", "znać",
    "powiedz", "pokaż", "znajdź", "mam", "masz", "ten", "ta", "już", "być",
    "swoje", "swoja", "swój", "chcę", "chce",
}


class IndexUnavailable(Exception):
    """No usable index at the given path (missing, empty, or without meta)."""


@dataclass
class Index:
    """Loaded, read-only view of an index."""
    db_path: Path
    spec: ModelSpec
    embed_dim: int
    paths: list[str] = field(default_factory=list)
    ords: list[int] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    vectors: np.ndarray = None  # (n_chunks, embed_dim), float32, normalized


def load_index(db_path: Path) -> Index:
    if not db_path.is_file():
        raise IndexUnavailable(f"no index at {db_path}")
    conn = store.open_readonly(db_path)
    try:
        meta = store.get_meta(conn)
        if not meta.get("model_name"):
            raise IndexUnavailable(f"index at {db_path} has no meta")
        rows = conn.execute("SELECT path, ord, heading, text, vector FROM chunks ORDER BY id").fetchall()
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
        paths=[r[0] for r in rows],
        ords=[r[1] for r in rows],
        headings=[r[2] or "" for r in rows],
        texts=[r[3] for r in rows],
        vectors=np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows]),
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
            "chunk": int(i),  # position in idx.texts, for callers that need the full text
        })
        if len(results) >= top_k:
            break
    return results


def keywords_from_query(query: str) -> list[str]:
    # Case-preserving pass first so all-caps acronyms (CV, AI, US) survive at
    # 2 characters, while genuine 2-letter stopwords (o, w, z, do...) drop.
    keywords = []
    for t in re.findall(r"\w+", query):
        low = t.lower()
        if low in STOPWORDS:
            continue
        if len(t) >= 3 or (t.isupper() and len(t) >= 2):
            keywords.append(low)
    return keywords


def keyword_search(corpus: Corpus, query: str, top_k: int) -> list[dict]:
    keywords = keywords_from_query(query)
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


def hybrid_search(idx: Index, corpus: Corpus, query: str, top_k: int) -> list[dict]:
    pool = max(top_k * 5, 40)
    semantic_hits = _best_per_path(semantic_search(idx, query, top_k=pool, min_score=-1.0))
    keyword_hits = keyword_search(corpus, query, top_k=pool)

    rrf: dict[str, float] = {}
    by_path: dict[str, dict] = {}
    for hits in (semantic_hits, keyword_hits):
        for rank, r in enumerate(hits):
            rrf[r["path"]] = rrf.get(r["path"], 0.0) + 1.0 / (RRF_K + rank + 1)
            by_path.setdefault(r["path"], r)

    fused = [{"score": round(score, 6), "path": path,
              "heading": by_path[path].get("heading"), "ord": by_path[path].get("ord"),
              "snippet": by_path[path].get("snippet"), "chunk": by_path[path].get("chunk")}
             for path, score in rrf.items()]
    fused.sort(key=lambda r: -r["score"])
    return fused[:top_k]
