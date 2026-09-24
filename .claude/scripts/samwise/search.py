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
# Three strategies:
#   - semantic: encode the query exactly as the index was built (model,
#     revision, query prefix, config overrides recorded in its meta) and rank
#     chunks by cosine similarity.
#   - grep:     keyword baseline — ranks whole files by keyword hit count.
#   - hybrid:   Reciprocal Rank Fusion (k=60) of the two.
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

from imladris import search as engine  # noqa: E402
from imladris.models import load_model  # noqa: E402,F401  (re-exported for the eval)
from index import brain_corpus, resolve_brain_path  # noqa: E402,F401  (Bilbo's brain/ rules)

SamwiseIndex = engine.Index

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


def grep_search(brain_dir: Path, query: str, top_k: int) -> list[dict]:
    return engine.keyword_search(brain_corpus(brain_dir), query, top_k)


def search(brain_dir: Path, query: str, strategy: str, top_k: int,
           min_score: float, idx: SamwiseIndex | None = None) -> list[dict]:
    if strategy == "grep":
        return grep_search(brain_dir, query, top_k)
    if idx is None:
        idx = load_index(brain_dir)
    if strategy == "semantic":
        return engine.semantic_search(idx, query, top_k, min_score)
    if strategy == "hybrid":
        return engine.hybrid_search(idx, brain_corpus(brain_dir), query, top_k)
    raise ValueError(f"unknown strategy: {strategy}")


def main():
    parser = argparse.ArgumentParser(
        description="S.A.M.W.I.S.E. — query-time reader over B.I.L.B.O.'s embedding index"
    )
    parser.add_argument("query", type=str, help="the natural-language question")
    parser.add_argument("--strategy", choices=["semantic", "grep", "hybrid"], default="semantic")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="semantic-only: drop hits below this cosine score")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    brain_dir = resolve_brain_path(PROJECT_DIR)
    results = search(brain_dir, args.query, args.strategy, args.top_k, args.min_score)

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
