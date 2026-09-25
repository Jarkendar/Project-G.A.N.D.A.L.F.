#!/usr/bin/env python3
# S.A.M.W.I.S.E. — SQL And Markdown Wading Into Semantic Embeddings.
#
# The reader. B.I.L.B.O. (.claude/scripts/bilbo/index.py) WRITES the index at
# brain/index/bilbo.db; Samwise only READS it — never a writer connection,
# never a rebuild.
#
# Retrieval itself lives in the imladris-rag engine (imladris.search); this
# adapter supplies brain/: where it is, what counts as knowledge (the same
# rules Bilbo indexes by), the calibrated threshold, and the CLI.
#
# Strategies:
#   - semantic:   encode the query exactly as the index was built (model,
#     revision, query prefix, config overrides recorded in its meta) and rank
#     chunks by cosine similarity.
#   - fts:        BM25 over blocks (SQLite FTS5), query words cut to a stem.
#   - hybrid-fts: Reciprocal Rank Fusion (k=60) of semantic and fts, per block.
#   - grep:       keyword baseline — ranks whole files by keyword hit count.
#   - hybrid:     RRF of semantic and grep (file level) — the older baseline.
# --diversify keeps only the best block of each file.
# --rerank KEY reorders the top RERANK_POOL blocks with a cross-encoder
# (imladris.rerank); off unless SAMWISE_RERANKER is set in gandalf.env.
#
# Usable two ways:
#   1. CLI:    ./search.py "query" --strategy semantic --top-k 8
#   2. Module: `import search; idx = search.load_index(brain_dir); ...` — the
#      eval harness uses this so the (heavy) model loads once for all queries.

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / "imladris-rag"))
sys.path.insert(0, str(PROJECT_DIR / ".claude" / "scripts" / "bilbo"))

from imladris import context as context_engine  # noqa: E402
from imladris import rerank as rerank_engine  # noqa: E402
from imladris import search as engine  # noqa: E402
from imladris.models import load_model  # noqa: E402,F401  (re-exported for the eval)
from index import brain_corpus, read_gandalf_env, resolve_brain_path  # noqa: E402,F401  (Bilbo's brain/ rules)

SamwiseIndex = engine.Index

# Words that carry no meaning in brain/ queries (PL + EN), for the keyword
# strategies. Config, not code: edit stopwords.txt.
STOPWORDS = engine.load_stopwords(Path(__file__).with_name("stopwords.txt"))

# Calibrated by eval/run_eval.py for the production index — granite-311m +
# chunker v2 since 2026-09-24 — against the 63-query golden set (F1-optimal:
# F1=0.645, precision=0.552, recall=0.775; IMPLEMENTATION.md Step 9, Index v2
# phase B). The value is model-specific: cosine scores of different models
# live on different scales (MiniLM's was 0.5047). Re-run the eval and update
# this constant whenever BILBO_EMBED_MODEL or the chunker changes.
#
# Known limitation (measured, not theoretical): broad "list everything about
# X" queries can legitimately score below any fixed cutoff on every relevant
# chunk. A score threshold cannot fully solve this — see samwise.md's
# workflow for the mitigation (widen --top-k / relax --min-score for
# enumerative-sounding questions).
DEFAULT_MIN_SCORE = 0.8684
DEFAULT_TOP_K = 8

# How --context orders its lead files. "zmax" uses the document-level vectors
# of an enriched index (BILBO_ENRICHMENT_USE=doc) and falls back to "blocks"
# on an index without them. Measured 2026-09-25: hit@1 .76 -> .78, MRR
# .83 -> .86 (IMPLEMENTATION.md Step 9, Index v2 phase D).
DEFAULT_FILE_RANK = "zmax"

# Optional cross-encoder over the top RERANK_POOL blocks of a ranked search
# (not --context yet). Off by default: on the Pi 5 bge-m3 costs ~52 s per
# query for a small gain — measured 2026-09-25 against semantic: hit@1 .76
# -> .76, MRR .82 -> .83, ans@5 .84 -> .92 (IMPLEMENTATION.md Step 9, Index v2
# phase E). Turn on with SAMWISE_RERANKER=bge-m3 on faster hardware.
RERANK_POOL = 20


def default_reranker() -> str | None:
    """SAMWISE_RERANKER from the environment or gandalf.env; empty = off."""
    import os
    return os.environ.get("SAMWISE_RERANKER") or read_gandalf_env(PROJECT_DIR).get("SAMWISE_RERANKER") or None


def default_project_dir() -> Path:
    return PROJECT_DIR


def load_index(brain_dir: Path, db_path: Path | None = None) -> SamwiseIndex:
    """db_path defaults to Bilbo's production index; the eval harness passes an
    experimental one (built with `index.py --db`) to compare variants."""
    db_path = db_path or brain_dir / "index" / "bilbo.db"
    try:
        return engine.load_index(db_path)
    except engine.IndexUnavailable as err:
        sys.exit(f"SAMWISE: {err} — run B.I.L.B.O. (.claude/scripts/bilbo/index.py) first.")


semantic_search = engine.semantic_search


def grep_search(brain_dir: Path, query: str, top_k: int, stopwords: frozenset = STOPWORDS) -> list[dict]:
    return engine.keyword_search(brain_corpus(brain_dir), query, top_k, stopwords)


STRATEGIES = ("semantic", "fts", "hybrid-fts", "grep", "hybrid")
DEFAULT_BUDGET = 1500  # tokens; Index v2 phase C4: answer in bundle 0.95 at this budget
DEFAULT_STEM = 5  # FTS query words are cut to this many characters (0 = whole words)


def search(brain_dir: Path, query: str, strategy: str, top_k: int,
           min_score: float, idx: SamwiseIndex | None = None,
           diversify: bool = False, stem: int = DEFAULT_STEM,
           fts_weight: float = 1.0, stopwords: frozenset = STOPWORDS,
           reranker: str | None = None) -> list[dict]:
    if strategy == "grep":
        return grep_search(brain_dir, query, top_k, stopwords)
    if idx is None:
        idx = load_index(brain_dir)
    pool = top_k * 4 if diversify else top_k  # room to drop same-file blocks
    if reranker:
        pool = max(pool, RERANK_POOL)
    if strategy == "semantic":
        results = engine.semantic_search(idx, query, pool, min_score)
    elif strategy == "fts":
        results = engine.fts_search(idx, query, pool, stem, stopwords)
    elif strategy == "hybrid-fts":
        results = engine.hybrid_fts_search(idx, query, pool, stem, fts_weight, stopwords)
    elif strategy == "hybrid":
        results = engine.hybrid_search(idx, brain_corpus(brain_dir), query, pool, stopwords)
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    if reranker:
        results = rerank_engine.rerank(rerank_engine.load_reranker(reranker), query, results,
                                       [idx.texts[r["chunk"]] for r in results])
    return engine.diversify(results, top_k) if diversify else results[:top_k]


def build_context(idx: SamwiseIndex, query: str, **options) -> list:
    """A token-budgeted bundle of passages (imladris.context.build_context),
    counted with the index's own tokenizer."""
    from imladris.models import token_counter
    return context_engine.build_context(idx, query, token_counter(load_model(idx.spec)), **options)


def main():
    parser = argparse.ArgumentParser(
        description="S.A.M.W.I.S.E. — query-time reader over B.I.L.B.O.'s embedding index"
    )
    parser.add_argument("query", type=str, help="the natural-language question")
    parser.add_argument("--strategy", choices=STRATEGIES, default="semantic")
    parser.add_argument("--diversify", action="store_true", help="at most one block per file")
    parser.add_argument("--stem", type=int, default=DEFAULT_STEM,
                        help="fts / hybrid-fts: cut query words to this many characters (0 = off)")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="semantic-only: drop hits below this cosine score")
    parser.add_argument("--rerank", choices=[*rerank_engine.RERANKER_REGISTRY, "off"], default=None,
                        help="ranked modes: reorder the top %d blocks with a cross-encoder "
                             "(default: SAMWISE_RERANKER; empty = off)" % RERANK_POOL)
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--context", action="store_true",
                        help="return a context bundle (widened passages with citations) "
                             "instead of ranked hits")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                        help="--context: token budget of the bundle")
    parser.add_argument("--no-links", action="store_true", help="--context: do not follow links")
    parser.add_argument("--file-rank", choices=context_engine.FILE_RANKS, default=DEFAULT_FILE_RANK,
                        help="--context: order lead files by best block, or also by document vectors")
    args = parser.parse_args()

    brain_dir = resolve_brain_path(PROJECT_DIR)
    if args.context:
        items = build_context(load_index(brain_dir), args.query, budget=args.budget,
                              links=not args.no_links, file_rank=args.file_rank)
        if args.format == "json":
            print(json.dumps([vars(it) for it in items], ensure_ascii=False, indent=2))
        else:
            if not items:
                print("SAMWISE: no hits.")
            for it in items:
                number = f"{it.section_no} " if it.section_no else ""
                where = f" § {number}{it.heading}" if it.kind != "document" else " (whole file)"
                lines = f" L{it.lines[0]}-{it.lines[1]}" if it.lines else ""
                note = "" if it.reason == "hit" else f" [{it.reason}]"
                print(f"=== {it.path}{where}{lines} — {it.privacy}, {it.tokens} tok, score {it.score}{note}")
                print(it.text)
                print()
        return
    reranker = default_reranker() if args.rerank is None else (None if args.rerank == "off" else args.rerank)
    results = search(brain_dir, args.query, args.strategy, args.top_k, args.min_score,
                     diversify=args.diversify, stem=args.stem, reranker=reranker)

    if args.format == "json":
        print(json.dumps([{k: v for k, v in r.items() if k != "chunk"} for r in results],
                         ensure_ascii=False, indent=2))
    else:
        if not results:
            print("SAMWISE: no hits.")
        for r in results:
            heading = f" § {r['heading']}" if r.get("heading") else ""
            print(f"{r['score']:>8}  {r['path']}{heading}")
            print(f"          {r['snippet']}")


if __name__ == "__main__":
    main()
