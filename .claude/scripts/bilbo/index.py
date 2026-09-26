#!/usr/bin/env python3
# B.I.L.B.O. — Bot Indexing Local Binary Objects.
#
# The indexer. Not a reactive agent — a background script, run by brain/'s
# post-commit / post-merge hooks. Bilbo only WRITES the index; S.A.M.W.I.S.E.
# READS it — that boundary is deliberate, see README.md's Bilbo/Samwise split.
#
# The engine lives in imladris-rag/ (chunking, models, store, incremental
# sync) and knows nothing about brain/. This adapter supplies what does:
# where brain/ is (BRAIN_PATH), what is not knowledge (index/, Smeagol's logs,
# per-folder CLAUDE.md), which model and chunker production uses
# (.claude/gandalf.env), and which brain/ commit an index reflects.
#
# Storage: a Qdrant collection (BILBO_INDEX, default
# http://127.0.0.1:6333/bilbo; the server: imladris-rag/docker-compose.yml) —
# regenerable from brain/. Only the enrichment cache lives in brain/index/
# (gitignored), outside brain/db/ on purpose — that folder holds owned
# operational databases (brain/db/CLAUDE.md).

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / "imladris-rag"))

from imladris import enrich, indexer, store  # noqa: E402
from imladris.chunking import CHUNKERS  # noqa: E402
from imladris.corpus import Corpus  # noqa: E402
from imladris.models import DEFAULT_MODEL, MODEL_REGISTRY, resolve_model  # noqa: E402

# brain/ privacy is folder-level first, then per file (brain/CLAUDE.md): these
# folders are private whatever a file says; knowledge/ is public unless the
# file says private; anything else follows the file, private when unstated.
ALWAYS_PRIVATE = {"core", "current", "conversations", "backlog", "_meta"}


def brain_privacy(rel_path: Path, frontmatter: dict) -> str:
    folder = rel_path.parts[0] if len(rel_path.parts) > 1 else ""
    if folder in ALWAYS_PRIVATE:
        return "private"
    if folder == "knowledge":
        return "private" if frontmatter.get("privacy") == "private" else "public"
    return frontmatter.get("privacy") or "private"


# What in brain/ is not knowledge: the index's own folder, Smeagol's logs (and
# privacy-sensitive), and per-folder CLAUDE.md files (operating instructions).
BRAIN_CORPUS_RULES = dict(
    exclude_top_dirs=frozenset({"index"}),
    exclude_prefixes=("current/smeagol",),
    exclude_names=frozenset({"CLAUDE.md"}),
    privacy_of=brain_privacy,
)


def read_gandalf_env(project_dir: Path) -> dict:
    """KEY=VALUE pairs from .claude/gandalf.env, taken literally (no shell
    quoting), so a JSON value such as BILBO_CHUNK_PARAMS needs no escaping."""
    values = {}
    try:
        for line in (project_dir / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def resolve_brain_path(project_dir: Path) -> Path:
    raw = read_gandalf_env(project_dir).get("BRAIN_PATH")
    if not raw:
        sys.exit("BILBO: BRAIN_PATH not set in .claude/gandalf.env — aborting.")
    path = Path(raw)
    if not path.is_absolute():
        path = project_dir / path
    path = path.resolve()
    if not path.is_dir():
        sys.exit(f"BILBO: resolved BRAIN_PATH does not exist: {path}")
    return path


DEFAULT_INDEX = "http://127.0.0.1:6333/bilbo"


def resolve_index_location(project_dir: Path, brain_dir: Path) -> str:
    """Where the production index lives: BILBO_INDEX (environment, then
    gandalf.env) as "<qdrant url>/<collection>", else DEFAULT_INDEX.
    `brain_dir` is unused since the SQLite index went; kept for callers."""
    return os.environ.get("BILBO_INDEX") or read_gandalf_env(project_dir).get("BILBO_INDEX") or DEFAULT_INDEX


def brain_corpus(brain_dir: Path) -> Corpus:
    return Corpus(root=brain_dir, **BRAIN_CORPUS_RULES)


def brain_head(brain_dir: Path) -> str | None:
    """Current HEAD commit of the brain/ repo, or None if it is not a git repo."""
    try:
        return subprocess.run(
            ["git", "-C", str(brain_dir), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main():
    parser = argparse.ArgumentParser(description="B.I.L.B.O. — embedding indexer for brain/")
    parser.add_argument("--rebuild", action="store_true", help="wipe and rebuild the full index")
    parser.add_argument("--path", type=str, default=None,
                        help="limit to one file or subdirectory (relative to BRAIN_PATH)")
    parser.add_argument("--model", type=str, default=None,
                        help="embedding model: a key of imladris.models.MODEL_REGISTRY ("
                             + ", ".join(MODEL_REGISTRY) + ") or a Hub name "
                             "(revision then from BILBO_EMBED_REVISION)")
    parser.add_argument("--chunker", choices=CHUNKERS, default=None,
                        help="v1: heading + ~90-word windows; "
                             "v2: structural blocks within token budgets (production)")
    parser.add_argument("--chunk-params", type=str, default=None,
                        help="chunker v2 only: JSON overriding "
                             "imladris.chunking.DEFAULT_CHUNK_PARAMS, e.g. "
                             "'{\"prefix\": \"path\", \"merge_tiny\": 40}'")
    parser.add_argument("--dry-run", action="store_true", help="report deltas without embedding or writing")
    parser.add_argument("--if-new-commits", action="store_true",
                        help="skip the run when brain/ HEAD equals the last indexed commit "
                             "(used by the post-commit/post-merge hooks in brain/)")
    parser.add_argument("--enrich", action="store_true",
                        help="ask an LLM (Claude Code CLI, Haiku) for each changed file's summary, "
                             "topics, keywords and section context, cached in brain/index/enrichment.db; "
                             "no embedding happens in this mode")
    parser.add_argument("--enrich-workers", type=int, default=4, help="--enrich: parallel CLI calls")
    parser.add_argument("--enrichment-use", type=str, default=None,
                        help="comma-separated uses of the enrichment in the vectors: doc, context "
                             "(default: BILBO_ENRICHMENT_USE; empty = none). When set, changed files "
                             "are enriched first, then embedded")
    parser.add_argument("--db", type=str, default=None,
                        help="write to this index instead of the production one (BILBO_INDEX): "
                             "<qdrant url>/<collection> — for variants compared by the Samwise eval")
    args = parser.parse_args()

    brain_dir = resolve_brain_path(PROJECT_DIR)
    corpus = brain_corpus(brain_dir)

    # Precedence: CLI flag > environment variable > .claude/gandalf.env > built-in
    # default. gandalf.env is what the post-commit hook runs with, so it is where
    # the production model and chunker are configured.
    genv = read_gandalf_env(PROJECT_DIR)
    setting = lambda key, default=None: os.environ.get(key) or genv.get(key) or default
    chunker = args.chunker or setting("BILBO_CHUNKER", "v1")
    raw_params = args.chunk_params or setting("BILBO_CHUNK_PARAMS")
    chunk_params = json.loads(raw_params) if raw_params else None
    spec = resolve_model(args.model or setting("BILBO_EMBED_MODEL", DEFAULT_MODEL),
                         os.environ.get("BILBO_EMBED_REVISION"))
    raw_use = args.enrichment_use if args.enrichment_use is not None else setting("BILBO_ENRICHMENT_USE", "")
    use = tuple(u.strip() for u in raw_use.split(",") if u.strip())

    scope = None
    if args.path:
        scope = (brain_dir / args.path).resolve()
        if not scope.exists():
            sys.exit(f"BILBO: --path does not exist under BRAIN_PATH: {scope}")

    def run_enrichment():
        cache = enrich.open_cache(brain_dir / "index" / "enrichment.db")
        started = time.time()
        counts = enrich.enrich_corpus(cache, corpus, enrich.ClaudeCliEnricher(), workers=args.enrich_workers,
                                      scope=scope, log=lambda msg: print(f"BILBO: {msg}", flush=True))
        print(f"BILBO: enrichment — {counts['enriched']} enriched, {counts['cached']} cached, "
              f"{counts['failed']} failed, in {time.time() - started:.0f}s.")
        data = enrich.load(cache)
        cache.close()
        return data

    if args.enrich:
        run_enrichment()
        return

    db_path = args.db or resolve_index_location(PROJECT_DIR, brain_dir)
    try:
        st = store.open_store(db_path)
    except ValueError as err:
        sys.exit(f"BILBO: {err}")
    try:
        st.get_meta()
    except Exception as err:  # a Qdrant index whose server is down; the next run catches up
        sys.exit(f"BILBO: index at {db_path} unreachable ({type(err).__name__}: {err}) — start Qdrant: "
                 f"docker compose -f imladris-rag/docker-compose.yml up -d")

    # Read HEAD before scanning: a commit landing mid-run then shows up as
    # "new" on the next check instead of being marked indexed unseen.
    head = brain_head(brain_dir)
    if args.if_new_commits and head and head == st.get_meta().get("last_indexed_commit"):
        print(f"BILBO: brain/ HEAD {head[:7]} already indexed — nothing to do.")
        st.close()
        return

    start = time.time()
    if args.dry_run:
        to_update, to_delete, unchanged = indexer.plan(st, corpus, scope, args.rebuild)
        print(f"BILBO (dry-run): {len(to_update)} to add/update, "
              f"{len(to_delete)} to delete, {unchanged} unchanged.")
        for rel in to_update:
            print(f"  update: {rel.as_posix()}")
        for path in to_delete:
            print(f"  delete: {path}")
        st.close()
        return

    # Enrich before embedding, so the vectors see this commit's enrichment.
    enrichment = run_enrichment() if use else None
    try:
        result = indexer.sync(st, corpus, spec, chunker, chunk_params, scope, args.rebuild,
                              log=lambda msg: print(f"BILBO: {msg}"), enrichment=enrichment, use=use)
    except (store.IndexMismatch, ValueError) as err:
        sys.exit(f"BILBO: {err}")
    print(f"BILBO: {result.updated} file(s) updated ({result.chunks} chunks), "
          f"{result.deleted} deleted, {result.unchanged} unchanged."
          + (f" {result.links} resolved links." if result.updated or result.deleted else ""))
    # Only a full-scope run covers everything HEAD contains; a --path run
    # leaves the rest unchecked, so it must not claim the commit.
    if head and scope is None:
        st.set_meta(last_indexed_commit=head)
    st.close()
    print(f"BILBO: done in {time.time() - start:.1f}s. Index: {db_path}")


if __name__ == "__main__":
    main()
