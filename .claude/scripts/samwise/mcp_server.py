#!/usr/bin/env python3
# S.A.M.W.I.S.E. as an MCP server — the same read-only retrieval as
# search.py, served as MCP tools so Gandalf (or any MCP client) calls it
# instead of shelling out.
#
# Why a server: search.py loads the embedding model on every call (~26 s on
# the Pi); here it loads once, on the first query, and later queries take
# well under a second.
#
# RAM: the model and the index live in a worker process (~2.2 GB loaded;
# granite-311m in float32 is 1.6 of it), the MCP server itself in ~80 MB
# without torch. After --idle-unload seconds without a call
# (SAMWISE_IDLE_UNLOAD, default 600; 0 = never) the worker is shut down and
# the next query starts a new one (~15 s). A process, not an in-process
# unload: dropping the model inside a process gave back only ~0.4 of the
# 2.2 GB — torch keeps the rest, whatever glibc is told (measured
# 2026-09-26).
#
# Transports:
#   - http (production): one shared process — the systemd user service
#     samwise-mcp.service on 127.0.0.1:8765/mcp — so every Claude Code
#     session, and later n8n, shares one copy of the model. Stateless: a
#     server restart does not break a client's session.
#   - stdio: one process per client; for trying it out by hand.
#
# Freshness: B.I.L.B.O. rewrites the index after every brain/ commit. Before
# each call the worker compares the index's per-file content hashes with the
# ones it loaded and reloads on any change, so it never answers from a stale
# copy.
#
# Read-only, like search.py: the store is opened read-only, nothing here
# writes to the index.
#
# Call log: one JSON line per tool call (tool, strategy, folders, cold start,
# latency, result count, status — never the query) in
# ~/.local/share/gandalf/samwise-calls.jsonl (SAMWISE_CALL_LOG overrides).

import argparse
import hashlib
import json
import multiprocessing
import os
import re
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search as samwise  # noqa: E402  (no torch at import: models load lazily)
from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp_types import ToolAnnotations  # noqa: E402

from imladris import search as engine  # noqa: E402
from imladris.rerank import RERANKER_REGISTRY  # noqa: E402

Reranker = Literal[tuple(RERANKER_REGISTRY) + ("off",)]
Strategy = Literal[samwise.STRATEGIES]

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
DEFAULT_IDLE_UNLOAD = 600  # seconds
DEFAULT_PORT = 8765

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


# --- worker process: holds the index and the models -------------------------

_worker: dict = {"idx": None, "fingerprint": None}


def _fingerprint(store) -> str:
    """Changes whenever Bilbo adds, rewrites or deletes a document."""
    hashes = store.stored_hashes()
    return hashlib.sha256(repr(sorted(hashes.items())).encode()).hexdigest()


def _index() -> engine.Index:
    """The loaded index, reloaded when the stored one has changed since.
    Raises engine.IndexUnavailable when there is none (or Qdrant is down)."""
    idx = _worker["idx"]
    if idx is not None:
        try:
            if _fingerprint(idx.store) == _worker["fingerprint"]:
                return idx
        except Exception:  # server went away: reopen below, which reports it
            pass
        idx.store.close()
        _worker["idx"] = None
    brain_dir = samwise.resolve_brain_path(samwise.PROJECT_DIR)
    location = samwise.resolve_index_location(samwise.PROJECT_DIR, brain_dir)
    idx = engine.load_index(location)
    _worker.update(idx=idx, fingerprint=_fingerprint(idx.store))
    return idx


def _unavailable(err: Exception) -> str:
    return (f"SAMWISE: index unavailable — {err}. If Qdrant is down: "
            "docker compose -f imladris-rag/docker-compose.yml up -d. "
            "Fall back to grep over brain/ and say so.")


def _run_context(query: str, budget: int, follow_links: bool, reranker: str | None,
                 folders: list[str]) -> str:
    try:
        idx = _index()
    except engine.IndexUnavailable as err:
        return _unavailable(err)
    items = samwise.build_context(idx, query, reranker=reranker, budget=budget,
                                  links=follow_links, file_rank=samwise.DEFAULT_FILE_RANK,
                                  folders=folders)
    if not items and folders:
        return f"SAMWISE: no hits under {', '.join(folders)} — check the folder names (paths relative to brain/)."
    return samwise.format_context(items)


def _run_search(query: str, strategy: str, top_k: int, min_score: float, diversify: bool,
                reranker: str | None) -> str:
    brain_dir = samwise.resolve_brain_path(samwise.PROJECT_DIR)
    try:
        idx = None if strategy == "grep" else _index()
    except engine.IndexUnavailable as err:
        return _unavailable(err)
    results = samwise.search(brain_dir, query, strategy, top_k, min_score, idx=idx,
                             diversify=diversify, reranker=reranker)
    return samwise.format_hits(results)


# --- server process: starts the worker on demand, stops it when idle ---------

_lock = threading.Lock()
_pool: dict = {"executor": None, "busy": 0, "last_used": time.monotonic()}


@contextmanager
def _executor():
    """The worker, started if needed (then `cold`: the model loads on this
    call); marked busy so the idle watcher leaves it."""
    with _lock:
        cold = _pool["executor"] is None
        if cold:
            _pool["executor"] = ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn"))
        _pool["busy"] += 1
        executor = _pool["executor"]
    try:
        yield executor, cold
    finally:
        with _lock:
            _pool["busy"] -= 1
            _pool["last_used"] = time.monotonic()


def _call_log_path() -> Path:
    raw = os.environ.get("SAMWISE_CALL_LOG") or samwise.read_gandalf_env(samwise.PROJECT_DIR).get("SAMWISE_CALL_LOG")
    return Path(raw).expanduser() if raw else Path.home() / ".local/share/gandalf/samwise-calls.jsonl"


def _log_call(record: dict):
    """One JSON line per tool call: what ran, how long, how many results —
    never the query text. Logging must never break a search."""
    try:
        path = _call_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with _lock, path.open("a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _count_results(tool: str, text: str) -> int:
    if text.startswith("SAMWISE:"):
        return 0
    if tool == "context":
        return sum(1 for line in text.splitlines() if line.startswith("=== "))
    return sum(1 for line in text.splitlines() if re.match(r"\s*-?\d+\.\d+  \S", line))  # "  0.8513  path"


def _call(tool: str, params: dict, fn, *args) -> str:
    started = time.perf_counter()
    with _executor() as (executor, cold):
        try:
            text = executor.submit(fn, *args).result()
        except BrokenProcessPool:  # the worker died (e.g. killed for RAM): start over next call
            with _lock:
                if _pool["executor"] is executor:
                    _pool["executor"] = None
            text = "SAMWISE: the search worker died (killed for RAM?) — retry once, then fall back to grep."
    status = ("ok" if not text.startswith("SAMWISE:") else
              "unavailable" if "index unavailable" in text else
              "worker-died" if "worker died" in text else "no-hits")
    _log_call({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": tool, **params, "cold_start": cold,
               "latency_ms": round((time.perf_counter() - started) * 1000), "results": _count_results(tool, text),
               "status": status})
    return text


def _watch_idle(seconds: int):
    while True:
        time.sleep(min(30, seconds))
        with _lock:
            idle = time.monotonic() - _pool["last_used"]
            if _pool["executor"] is None or _pool["busy"] or idle < seconds:
                continue
            executor, _pool["executor"] = _pool["executor"], None
        executor.shutdown(wait=True)


def _reranker(rerank: str | None) -> str | None:
    if rerank is None:
        return samwise.default_reranker()
    return None if rerank == "off" else rerank


@server.tool(annotations=READ_ONLY)
def context(query: str, budget: int = samwise.DEFAULT_BUDGET, follow_links: bool = True,
            folders: list[str] | None = None, rerank: Reranker | None = None) -> str:
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

    `folders` (path prefixes relative to brain/, e.g. ["knowledge/projects/"]) keeps
    only files under them — a SECOND call, never the first: after reading a first
    bundle for a question about a category (all my projects, trips, races, games),
    when its hits point at the folder where the members live but the bundle covers
    few of them. Measured as a second step: expected files read 103 -> 107 of 127,
    multi-file questions 22 -> 26 of 42. As a first call, with the folder guessed
    from its name, it hid answers and lost (multi hit@5 .79 -> .64).
    """
    reranker = _reranker(rerank)
    return _call("context", {"folders": len(folders or ()), "budget": budget, "rerank": reranker},
                 _run_context, query, budget, follow_links, reranker, list(folders or ()))


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
    reranker = _reranker(rerank)
    return _call("search", {"strategy": strategy, "wide": wide, "top_k": top_k, "rerank": reranker},
                 _run_search, query, strategy, top_k, min_score, diversify, reranker)


def default_idle_unload() -> int:
    raw = os.environ.get("SAMWISE_IDLE_UNLOAD") or samwise.read_gandalf_env(samwise.PROJECT_DIR).get(
        "SAMWISE_IDLE_UNLOAD")
    return int(raw) if raw else DEFAULT_IDLE_UNLOAD


def main():
    parser = argparse.ArgumentParser(description="S.A.M.W.I.S.E. — retrieval over brain/ as MCP tools")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="http: interface to bind")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="http: port (path /mcp)")
    parser.add_argument("--idle-unload", type=int, default=None,
                        help="seconds without a call before the model and index are dropped "
                             "(default: SAMWISE_IDLE_UNLOAD or %d; 0 = never)" % DEFAULT_IDLE_UNLOAD)
    args = parser.parse_args()

    idle = default_idle_unload() if args.idle_unload is None else args.idle_unload
    if idle > 0:
        threading.Thread(target=_watch_idle, args=(idle,), daemon=True, name="idle-unload").start()
    if args.transport == "http":
        server.run("streamable-http", host=args.host, port=args.port, stateless_http=True)
    else:
        server.run("stdio")


if __name__ == "__main__":
    main()
