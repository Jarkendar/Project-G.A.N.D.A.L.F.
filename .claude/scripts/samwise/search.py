#!/usr/bin/env python3
# S.A.M.W.I.S.E. — SQL And Markdown Wading Into Semantic Embeddings.
#
# The reader. B.I.L.B.O. (.claude/scripts/bilbo/index.py) WRITES the embedding
# index at brain/index/bilbo.db; Samwise only READS it — encodes the query with
# the same pinned model recorded in the index's `meta` table, cosine-ranks
# chunks against it, and returns ranked paths + snippets. Neither role crosses
# into the other: Samwise never touches brain/index/ with a writer connection,
# never rebuilds or re-embeds the corpus.
#
# Three strategies, one script, so the same code path serves both the live
# `samwise` sub-agent and the comparative eval harness (eval/run_eval.py):
#   - semantic: encode the query, rank brain/ chunks by cosine similarity
#     (vectors are pre-normalized by Bilbo, so cosine == dot product).
#   - grep:     keyword baseline — what Gandalf's Step 2b does today without
#     Samwise. Ranks whole files by keyword hit count.
#   - hybrid:   Reciprocal Rank Fusion (k=60) of the two rankings above.
#
# Usable two ways:
#   1. CLI:    ./search.py "query" --strategy semantic --top-k 8
#   2. Module: `import search; idx = search.load_index(brain_dir); ...` — the
#      eval harness uses this so the (heavy) model loads once for all queries
#      instead of once per subprocess invocation.

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# --- Corpus rules — must match Bilbo's exactly, or Samwise would rank chunks
# Bilbo never embedded, or grep files Bilbo excludes as non-knowledge. ---------
EXCLUDED_DIR_PARTS = {"index"}
EXCLUDED_SUBPATHS = ("current/smeagol",)
EXCLUDED_FILENAMES = {"CLAUDE.md"}

# Calibrated in Part 3 (eval/run_eval.py) against the golden set. 0.0 = no
# filtering, i.e. always return top-k regardless of score, until calibrated.
DEFAULT_MIN_SCORE = 0.0
DEFAULT_TOP_K = 8
RRF_K = 60  # standard Reciprocal Rank Fusion constant

SNIPPET_CHARS = 240

STOPWORDS = {
    # English function words / query-pattern filler ("what do I know about...")
    "the", "and", "for", "with", "this", "that", "from", "have", "what",
    "about", "your", "how", "when", "where", "which", "does", "did", "was",
    "were", "are", "into", "over", "under", "who", "whom", "will", "can",
    "know", "tell", "find", "show", "any",
    # Polish function words / query-pattern filler ("co wiem o... / jakie mam...")
    # — an LLM curating keywords by hand would skip these too; extending the
    # list is how a mechanical extractor approximates that judgment.
    "wiem", "jak", "jakie", "jakich", "jaki", "jaka", "czy", "się", "nie",
    "dla", "tego", "tym", "oraz", "moje", "moja", "mój", "moim", "jest",
    "były", "była", "był", "coś", "tam", "tutaj", "znam", "znaj", "znać",
    "powiedz", "pokaż", "znajdź", "mam", "masz", "ten", "ta", "już", "być",
    "swoje", "swoja", "swój", "chcę", "chce",
}


# --- Environment --------------------------------------------------------------
# Copy of Bilbo's resolve_brain_path (index.py), not a cross-import — the
# writer and reader are deliberately independent scripts.

def resolve_brain_path(project_dir: Path) -> Path:
    env_file = project_dir / ".claude" / "gandalf.env"
    raw = None
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("BRAIN_PATH="):
                raw = line.split("=", 1)[1].strip()
                break
    except OSError:
        pass
    if not raw:
        sys.exit("SAMWISE: BRAIN_PATH not set in .claude/gandalf.env — aborting.")
    path = Path(raw)
    if not path.is_absolute():
        path = project_dir / path
    path = path.resolve()
    if not path.is_dir():
        sys.exit(f"SAMWISE: resolved BRAIN_PATH does not exist: {path}")
    return path


def default_project_dir() -> Path:
    # this file: .claude/scripts/samwise/search.py -> parents[3] == project root
    return Path(__file__).resolve().parents[3]


# --- Discovery (mirrors Bilbo's is_excluded/discover_files) -------------------

def is_excluded(rel_path: Path) -> bool:
    parts = rel_path.parts
    if parts and parts[0] in EXCLUDED_DIR_PARTS:
        return True
    posix = rel_path.as_posix()
    if any(posix.startswith(sub) for sub in EXCLUDED_SUBPATHS):
        return True
    if rel_path.name in EXCLUDED_FILENAMES:
        return True
    return False


def discover_files(brain_dir: Path) -> list[Path]:
    found = []
    for p in brain_dir.rglob("*.md"):
        if not p.is_file():
            continue
        rel = p.relative_to(brain_dir)
        if is_excluded(rel):
            continue
        found.append(rel)
    return sorted(found, key=lambda r: r.as_posix())


# --- Index (read-only) --------------------------------------------------------

@dataclass
class SamwiseIndex:
    """Loaded, read-only view of brain/index/bilbo.db."""
    brain_dir: Path
    db_path: Path
    model_name: str
    model_revision: str
    embed_dim: int
    paths: list[str] = field(default_factory=list)
    ords: list[int] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)
    vectors: np.ndarray = None  # shape (n_chunks, embed_dim), float32, normalized


def load_index(brain_dir: Path) -> SamwiseIndex:
    db_path = brain_dir / "index" / "bilbo.db"
    if not db_path.is_file():
        sys.exit(
            f"SAMWISE: no index at {db_path} — run B.I.L.B.O. "
            f"(.claude/scripts/bilbo/index.py) first."
        )
    # Read-only URI connection: Samwise is never a writer of this database.
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        if not meta.get("model_name"):
            sys.exit(f"SAMWISE: index at {db_path} has no meta — run Bilbo to build it.")
        rows = conn.execute(
            "SELECT path, ord, heading, text, vector FROM chunks ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        sys.exit(f"SAMWISE: index at {db_path} has no chunks — run Bilbo to build it.")

    embed_dim = int(meta.get("embed_dim", "0"))
    vectors = np.stack(
        [np.frombuffer(r[4], dtype=np.float32) for r in rows]
    ) if rows else np.zeros((0, embed_dim), dtype=np.float32)

    return SamwiseIndex(
        brain_dir=brain_dir,
        db_path=db_path,
        model_name=meta["model_name"],
        model_revision=meta.get("model_revision", ""),
        embed_dim=embed_dim,
        paths=[r[0] for r in rows],
        ords=[r[1] for r in rows],
        headings=[r[2] or "" for r in rows],
        texts=[r[3] for r in rows],
        vectors=vectors,
    )


_model_cache = {}


def load_model(model_name: str, revision: str):
    """Lazy, cached load of the sentence-transformers model. Kept out of the
    module's top-level imports so `--strategy grep` never pays the (heavy)
    torch/sentence-transformers import cost."""
    key = (model_name, revision)
    if key not in _model_cache:
        from sentence_transformers import SentenceTransformer
        _model_cache[key] = SentenceTransformer(model_name, revision=revision)
    return _model_cache[key]


def embed_query(idx: SamwiseIndex, query: str) -> np.ndarray:
    model = load_model(idx.model_name, idx.model_revision)
    vec = model.encode([query], normalize_embeddings=True)[0]
    return vec.astype(np.float32)


def make_snippet(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= SNIPPET_CHARS:
        return collapsed
    return collapsed[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


# --- Strategy: semantic -------------------------------------------------------

def semantic_search(idx: SamwiseIndex, query: str, top_k: int, min_score: float) -> list[dict]:
    if idx.vectors.shape[0] == 0:
        return []
    query_vec = embed_query(idx, query)
    scores = idx.vectors @ query_vec  # normalized vectors -> cosine similarity
    order = np.argsort(-scores)
    results = []
    for i in order:
        score = float(scores[i])
        if score < min_score:
            break  # order is descending, so nothing further clears the bar
        results.append({
            "score": round(score, 4),
            "path": idx.paths[i],
            "heading": idx.headings[i],
            "ord": idx.ords[i],
            "snippet": make_snippet(idx.texts[i]),
        })
        if len(results) >= top_k:
            break
    return results


# --- Strategy: grep (baseline — what Gandalf's Step 2b does without Samwise) --

def keywords_from_query(query: str) -> list[str]:
    # Case-preserving pass first so all-caps acronyms (CV, AI, US) survive even
    # at 2 characters — lowercasing before the length check would drop them
    # alongside genuine 2-letter stopwords (o, w, z, do, na, i, a...).
    tokens = re.findall(r"\w+", query)
    keywords = []
    for t in tokens:
        low = t.lower()
        if low in STOPWORDS:
            continue
        if len(t) >= 3 or (t.isupper() and len(t) >= 2):
            keywords.append(low)
    return keywords


def grep_search(brain_dir: Path, query: str, top_k: int) -> list[dict]:
    keywords = keywords_from_query(query)
    if not keywords:
        return []
    results = []
    for rel in discover_files(brain_dir):
        abs_path = brain_dir / rel
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lower = text.lower()
        count = sum(lower.count(kw) for kw in keywords)
        if count == 0:
            continue
        # Snippet: first line containing any keyword, for a representative excerpt.
        snippet = next(
            (line.strip() for line in text.splitlines()
             if any(kw in line.lower() for kw in keywords) and line.strip()),
            text.strip().splitlines()[0] if text.strip() else "",
        )
        results.append({
            "score": count,
            "path": rel.as_posix(),
            "heading": None,
            "ord": None,
            "snippet": make_snippet(snippet),
        })
    results.sort(key=lambda r: -r["score"])
    return results[:top_k]


# --- Strategy: hybrid (Reciprocal Rank Fusion of semantic + grep) -------------

def _dedup_by_path_keep_best(results: list[dict]) -> list[dict]:
    """Semantic results are per-chunk; collapse to one (best-scoring) row per
    path before rank-fusing with grep's per-file results."""
    best: dict[str, dict] = {}
    for rank, r in enumerate(results):
        if r["path"] not in best:
            best[r["path"]] = r
    return list(best.values())


def hybrid_search(idx: SamwiseIndex, brain_dir: Path, query: str, top_k: int) -> list[dict]:
    # Pull generous candidate pools from both strategies so RRF has enough to
    # fuse over, independent of the final top_k requested.
    pool = max(top_k * 5, 40)
    semantic_hits = _dedup_by_path_keep_best(
        semantic_search(idx, query, top_k=pool, min_score=-1.0)
    )
    grep_hits = grep_search(brain_dir, query, top_k=pool)

    rrf_scores: dict[str, float] = {}
    by_path: dict[str, dict] = {}
    for rank, r in enumerate(semantic_hits):
        rrf_scores[r["path"]] = rrf_scores.get(r["path"], 0.0) + 1.0 / (RRF_K + rank + 1)
        by_path.setdefault(r["path"], r)
    for rank, r in enumerate(grep_hits):
        rrf_scores[r["path"]] = rrf_scores.get(r["path"], 0.0) + 1.0 / (RRF_K + rank + 1)
        by_path.setdefault(r["path"], r)

    fused = []
    for path, score in rrf_scores.items():
        base = by_path[path]
        fused.append({
            "score": round(score, 6),
            "path": path,
            "heading": base.get("heading"),
            "ord": base.get("ord"),
            "snippet": base.get("snippet"),
        })
    fused.sort(key=lambda r: -r["score"])
    return fused[:top_k]


# --- Dispatch ------------------------------------------------------------------

def search(brain_dir: Path, query: str, strategy: str, top_k: int,
           min_score: float, idx: "SamwiseIndex | None" = None) -> list[dict]:
    if strategy == "grep":
        return grep_search(brain_dir, query, top_k)
    if idx is None:
        idx = load_index(brain_dir)
    if strategy == "semantic":
        return semantic_search(idx, query, top_k, min_score)
    if strategy == "hybrid":
        return hybrid_search(idx, brain_dir, query, top_k)
    raise ValueError(f"unknown strategy: {strategy}")


# --- CLI -----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="S.A.M.W.I.S.E. — query-time reader over B.I.L.B.O.'s embedding index"
    )
    parser.add_argument("query", type=str, help="the natural-language question")
    parser.add_argument("--strategy", choices=["semantic", "grep", "hybrid"],
                         default="semantic")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                         help="semantic-only: drop hits below this cosine score")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    args = parser.parse_args()

    project_dir = default_project_dir()
    brain_dir = resolve_brain_path(project_dir)

    results = search(brain_dir, args.query, args.strategy, args.top_k, args.min_score)

    if args.format == "json":
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            print("SAMWISE: no hits.")
        for r in results:
            heading = f" § {r['heading']}" if r.get("heading") else ""
            print(f"{r['score']:>8}  {r['path']}{heading}")
            print(f"          {r['snippet']}")


if __name__ == "__main__":
    main()
