#!/usr/bin/env python3
# S.A.M.W.I.S.E. as an MCP server — the same read-only retrieval as
# search.py, served over stdio so Gandalf (or any MCP client) calls it as a
# tool instead of shelling out.
#
# Why a server: search.py loads the embedding model on every call (~26 s on
# the Pi); here it loads once, on the first query — a session that never
# searches never pays for it in RAM — and later queries take well under a
# second.
#
# Freshness: B.I.L.B.O. rewrites the index after every brain/ commit. Before
# each call the server compares the index's per-file content hashes with the
# ones it loaded and reloads on any change, so it never answers from a stale
# copy.
#
# Read-only, like search.py: the store is opened read-only, nothing here
# writes to the index.
#
# Run by Claude Code from .mcp.json; by hand: `mcp_server.py` (stdio).

import hashlib
import sys
import threading
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search as samwise  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp_types import ToolAnnotations  # noqa: E402

from imladris import search as engine  # noqa: E402
from imladris.rerank import RERANKER_REGISTRY  # noqa: E402

Reranker = Literal[tuple(RERANKER_REGISTRY) + ("off",)]
Strategy = Literal[samwise.STRATEGIES]

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

server = MCPServer(
    name="samwise",
    log_level="WARNING",  # no per-request HTTP chatter from the Qdrant client
    instructions=(
        "S.A.M.W.I.S.E. — semantic search over the owner's personal knowledge base (brain/). "
        "Use `context` first for any open-ended question about the owner's notes, people, "
        "places, projects, health or knowledge; use `search` for ranked hits or a wide candidate "
        "list. Results carry paths relative to brain/ — Read the files for the full picture. "
        "Paths under core/ and current/ are PRIVATE."
    ),
)

_lock = threading.Lock()
_state: dict = {"idx": None, "fingerprint": None}


def _fingerprint(store) -> str:
    """Changes whenever Bilbo adds, rewrites or deletes a document."""
    hashes = store.stored_hashes()
    return hashlib.sha256(repr(sorted(hashes.items())).encode()).hexdigest()


def _index() -> engine.Index:
    """The loaded index, reloaded when the stored one has changed since.
    Raises engine.IndexUnavailable when there is none (or Qdrant is down)."""
    with _lock:
        idx = _state["idx"]
        if idx is not None:
            try:
                if _fingerprint(idx.store) == _state["fingerprint"]:
                    return idx
            except Exception:  # server went away: reopen below, which reports it
                pass
            idx.store.close()
            _state["idx"] = None
        brain_dir = samwise.resolve_brain_path(samwise.PROJECT_DIR)
        location = samwise.resolve_index_location(samwise.PROJECT_DIR, brain_dir)
        idx = engine.load_index(location)
        _state.update(idx=idx, fingerprint=_fingerprint(idx.store))
        return idx


def _reranker(rerank: str | None) -> str | None:
    if rerank is None:
        return samwise.default_reranker()
    return None if rerank == "off" else rerank


def _unavailable(err: Exception) -> str:
    return (f"SAMWISE: index unavailable — {err}. If Qdrant is down: "
            "docker compose -f imladris-rag/docker-compose.yml up -d. "
            "Fall back to grep over brain/ and say so.")


@server.tool(annotations=READ_ONLY)
def context(query: str, budget: int = samwise.DEFAULT_BUDGET, follow_links: bool = True,
            rerank: Reranker | None = None) -> str:
    """Default retrieval: a token-budgeted bundle of passages that answer the question.

    The best block of each of the top 3 files first, then further hits by score, each
    widened to its whole section when short (or the whole file), plus files linked
    to/from the lead files when they score close to the top. Every passage is headed
    `=== path § section Lstart-end — privacy, tokens, score [reason]` — cite from it.
    Measured: the answer is inside the bundle for 95% of golden-set queries.

    Do not raise `budget` for broad "list everything about X" questions — it barely
    helps (the missing files rank 30th-85th); run `search` with `wide=True` instead.
    `follow_links=False` if links pull in noise. `rerank="bge-m3"` reorders the top 20
    blocks with a cross-encoder but costs ~1 min per query on the Pi and did not help
    this mode when measured — only on explicit request.
    """
    try:
        idx = _index()
    except engine.IndexUnavailable as err:
        return _unavailable(err)
    items = samwise.build_context(idx, query, reranker=_reranker(rerank), budget=budget,
                                  links=follow_links, file_rank=samwise.DEFAULT_FILE_RANK)
    return samwise.format_context(items)


@server.tool(annotations=READ_ONLY)
def search(query: str, strategy: Strategy = "semantic", top_k: int = samwise.DEFAULT_TOP_K,
           min_score: float = samwise.DEFAULT_MIN_SCORE, diversify: bool = False,
           wide: bool = False, rerank: Reranker | None = None) -> str:
    """Ranked hits (score, path, section, snippet) — the snippet locates, Read the file.

    - Point lookup (one document answers it): the defaults. `min_score` 0.845 leans to
      recall (golden set: precision .37, recall .93), so expect some noise and judge it.
      Scores sit high and close together (relevant ~0.87-0.91) — read the ranking, not
      the absolute number.
    - Broad / enumerative ("what are my side-projects", plural nouns, "all"): `wide=True`
      = top 20, no threshold, one block per file. Relevant files can score below any
      cutoff; scan the list, group by path, and Read anything plausibly on-topic.
    - Exact names, numbers, identifiers: also try `strategy="fts"` (BM25, Polish prefix
      matching) as a second look — weaker than semantic on its own.
    - `strategy="grep"`: keyword baseline over the files, no index needed.
    - `rerank="bge-m3"`: better top 5 (answer in top 5 .84 -> .92) at ~1 min per query
      on the Pi — only on explicit request or when the default ranking clearly missed.
    """
    if wide:
        top_k, min_score, diversify = max(top_k, 20), 0.0, True
    brain_dir = samwise.resolve_brain_path(samwise.PROJECT_DIR)
    try:
        idx = None if strategy == "grep" else _index()
    except engine.IndexUnavailable as err:
        return _unavailable(err)
    results = samwise.search(brain_dir, query, strategy, top_k, min_score, idx=idx,
                             diversify=diversify, reranker=_reranker(rerank))
    return samwise.format_hits(results)


if __name__ == "__main__":
    server.run("stdio")
