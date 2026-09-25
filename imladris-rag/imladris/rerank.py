"""Rerankers: a cross-encoder reads the query and one passage together and
scores their relevance — slower than comparing two precomputed vectors, so
it only reorders a short list the bi-encoder already found.

Models are pinned to a Hub commit and loaded in float32 (the Pi 5 has no
bf16). Measured on a Pi 5 over a 20-block pool (IMPLEMENTATION.md Step 9,
Index v2 phase E): bge-m3 ~52 s per query, pl-base ~12.6 s — both opt-in."""

from dataclasses import dataclass

import numpy as np

RERANKER_REGISTRY = {
    "bge-m3": {"name": "BAAI/bge-reranker-v2-m3",
               "revision": "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"},
    "pl-base": {"name": "sdadas/polish-reranker-base-ranknet",
                "revision": "026118bf46c13bba7e735eef4f533f98e9d044f1"},
}

# Blocks are ~256 tokens plus a title/heading prefix; the query adds a few
# dozen. 512 fits every pair without paying for an unused window.
MAX_LENGTH = 512


@dataclass(frozen=True)
class RerankerSpec:
    name: str
    revision: str
    trust_remote_code: bool = False


def resolve_reranker(key: str) -> RerankerSpec:
    if key not in RERANKER_REGISTRY:
        raise ValueError(f"unknown reranker {key!r}; known: {', '.join(RERANKER_REGISTRY)}")
    return RerankerSpec(**RERANKER_REGISTRY[key])


class Reranker:
    """`score(query, passages)` -> relevance per passage, higher is better.
    Scores are comparable within one query, not across models."""

    def __init__(self, spec: RerankerSpec, batch_size: int = 8):
        import torch
        from sentence_transformers import CrossEncoder
        self.spec, self.batch_size = spec, batch_size
        self._model = CrossEncoder(spec.name, revision=spec.revision, max_length=MAX_LENGTH,
                                   trust_remote_code=spec.trust_remote_code,
                                   model_kwargs={"dtype": torch.float32})

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        if not passages:
            return np.zeros(0, dtype=np.float32)
        return np.asarray(self._model.predict([(query, p) for p in passages], batch_size=self.batch_size,
                                              show_progress_bar=False), dtype=np.float32)


_cache: dict = {}


def load_reranker(key: str) -> Reranker:
    if key not in _cache:
        _cache[key] = Reranker(resolve_reranker(key))
    return _cache[key]


def rerank(reranker: Reranker, query: str, hits: list[dict], texts: list[str]) -> list[dict]:
    """Reorder `hits` (with their full `texts`) by reranker score; each hit
    gains "rerank_score" and keeps its original "score"."""
    scores = reranker.score(query, texts)
    for hit, s in zip(hits, scores.tolist()):
        hit["rerank_score"] = round(s, 4)
    return [hits[i] for i in np.argsort(-scores, kind="stable")]
