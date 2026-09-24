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
# Storage: brain/index/bilbo.db (SQLite, gitignored, regenerable). Outside
# brain/db/ on purpose — that folder holds owned operational databases
# (brain/db/CLAUDE.md).

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / "imladris-rag"))

from imladris import indexer, store  # noqa: E402
from imladris.chunking import CHUNKERS  # noqa: E402
from imladris.corpus import Corpus  # noqa: E402
from imladris.models import DEFAULT_MODEL, MODEL_REGISTRY, resolve_model  # noqa: E402

# What in brain/ is not knowledge: the index's own folder, Smeagol's logs (and
# privacy-sensitive), and per-folder CLAUDE.md files (operating instructions).
BRAIN_CORPUS_RULES = dict(
    exclude_top_dirs=frozenset({"index"}),
    exclude_prefixes=("current/smeagol",),
    exclude_names=frozenset({"CLAUDE.md"}),
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
    parser.add_argument("--db", type=str, default=None,
                        help="write to this index instead of brain/index/bilbo.db — "
                             "for experimental variants compared by the Samwise eval")
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

    scope = None
    if args.path:
        scope = (brain_dir / args.path).resolve()
        if not scope.exists():
            sys.exit(f"BILBO: --path does not exist under BRAIN_PATH: {scope}")

    db_path = Path(args.db).resolve() if args.db else brain_dir / "index" / "bilbo.db"
    conn = store.open_store(db_path)

    # Read HEAD before scanning: a commit landing mid-run then shows up as
    # "new" on the next check instead of being marked indexed unseen.
    head = brain_head(brain_dir)
    if args.if_new_commits and head and head == store.get_meta(conn).get("last_indexed_commit"):
        print(f"BILBO: brain/ HEAD {head[:7]} already indexed — nothing to do.")
        conn.close()
        return

    start = time.time()
    if args.dry_run:
        to_update, to_delete, unchanged = indexer.plan(conn, corpus, scope, args.rebuild)
        print(f"BILBO (dry-run): {len(to_update)} to add/update, "
              f"{len(to_delete)} to delete, {unchanged} unchanged.")
        for rel in to_update:
            print(f"  update: {rel.as_posix()}")
        for path in to_delete:
            print(f"  delete: {path}")
        conn.close()
        return

    try:
        result = indexer.sync(conn, corpus, spec, chunker, chunk_params, scope, args.rebuild,
                              log=lambda msg: print(f"BILBO: {msg}"))
    except (store.IndexMismatch, ValueError) as err:
        sys.exit(f"BILBO: {err}")
    print(f"BILBO: {result.updated} file(s) updated ({result.chunks} chunks), "
          f"{result.deleted} deleted, {result.unchanged} unchanged.")
    # Only a full-scope run covers everything HEAD contains; a --path run
    # leaves the rest unchecked, so it must not claim the commit.
    if head and scope is None:
        store.set_meta(conn, last_indexed_commit=head)
    conn.close()
    print(f"BILBO: done in {time.time() - start:.1f}s. Index: {db_path}")


if __name__ == "__main__":
    main()
