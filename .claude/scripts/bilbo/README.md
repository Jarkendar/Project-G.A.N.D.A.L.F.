# B.I.L.B.O. — Bot Indexing Local Binary Objects

The indexer. Per README.md: *"Not a reactive agent — runs in the background as
a scheduled task. Walks watched directories, detects new or modified files,
chunks them, and stores them in the knowledge base."*

Bilbo **writes** the embedding index. It never answers a query — that's
**S.A.M.W.I.S.E.**'s job (`.claude/scripts/samwise/search.py`, served to
Gandalf as MCP tools by `mcp_server.py`): encode the query with the same pinned model,
rank `brain/` chunks by cosine similarity against `chunks.vector`, and return
ranked paths + snippets for Claude to `Read` deeper. Bilbo builds the index;
Samwise reads it. Neither role crosses into the other.

## Where the code lives

Since 2026-09-24 the engine — chunking, models, SQLite store, incremental
sync — is the `imladris-rag/` package at the repo root (see its README),
written to know nothing about brain/. `index.py` is the brain/ adapter: it
resolves `BRAIN_PATH`, defines what is not knowledge (`index/`,
`current/smeagol/`, per-folder `CLAUDE.md`), reads the production model and
chunker from `.claude/gandalf.env`, applies brain/'s folder-first privacy
rules (`brain_privacy`: core/, current/, conversations/, backlog/, _meta/
always private; knowledge/ public unless the file says private), records the
indexed brain/ commit for the hook, and keeps the CLI below unchanged.

The index (schema 2) holds more than vectors: each file's section tree with
line ranges, its frontmatter and effective privacy, and the links between
files — see `imladris-rag/imladris/store.py`.

## What it does

1. Walks `brain/` for `*.md` files, excluding `current/smeagol/` (Smeagol's
   logs — not knowledge), `index/` (its own output), and every per-folder
   `CLAUDE.md` (operating instructions, not retrievable knowledge).
2. Hashes each file's content and compares against the last-indexed hash
   stored in the index. **Unchanged files are skipped entirely —
   zero re-embedding cost.** Only new/changed files get (re)chunked and
   (re)embedded; deleted files have their chunks removed.
3. Chunks each file — production uses **chunker v2** (see "Models and
   chunkers" below): structural blocks packed within one section up to 256
   tokens, each prefixed with the file title and full heading path. Chunker
   v1 (heading + ~90-word windows) remains for reference.
4. Embeds all changed chunks in one batched `model.encode(...)` call
   (normalized vectors, so cosine similarity = dot product at query time).
5. Upserts everything into the index `BILBO_INDEX` names in `gandalf.env`:
   the Qdrant collection `http://127.0.0.1:6333/bilbo` in production (server:
   `imladris-rag/docker-compose.yml`), or `brain/index/bilbo.db` (SQLite —
   outside `brain/db/`, which is G.I.M.L.I.'s access monopoly per
   `brain/db/CLAUDE.md`) when unset. If Qdrant is down the run exits with a
   message; the next run catches up, since indexing is incremental.

## Running it

```bash
cd .claude/scripts/bilbo
python3 -m venv .venv          # gitignored, not committed
source .venv/bin/activate
pip install -r requirements.txt
python index.py                # incremental sync
python index.py --dry-run      # show what would change, without embedding
python index.py --path knowledge/career  # limit to one file/subtree
python index.py --rebuild      # wipe and re-embed everything
```

The first run downloads the pinned model revision to the local
Hugging Face cache (`~/.cache/huggingface/...`, outside this repo — never
committed). Subsequent runs reuse the cached weights; no repeated download.

### On the Raspberry Pi (aarch64): install the CPU build of torch

A plain `pip install -r requirements.txt` resolves torch to the **CUDA**
build even on a Pi — PyPI's `aarch64` wheels now ship CUDA 13 for ARM server
GPUs (Grace/Thor), and pull ~4 GB of `nvidia-*` packages the Pi can never
use. Install the CPU wheel explicitly:

```bash
pip install -r requirements.txt
pip uninstall -y $(pip freeze | grep -E '^(nvidia|cuda|triton)' | cut -d= -f1)
pip install --force-reinstall --no-deps torch==2.14.0 \
    --index-url https://download.pytorch.org/whl/cpu
python -c "import torch; print(torch.__version__)"   # expect ...+cpu
```

Venv size: **5.6 GB → 1.3 GB**. `pip check` stays clean — the CPU wheel
declares no `nvidia-*` dependencies. This is not pinned in
`requirements.txt` because the wheel lives on a separate index; the
`requirements.txt` pin (`sentence-transformers`, `numpy`) still holds.

## Automatic reindex on commit

brain/'s `core.hooksPath` points at `.claude/hooks/brain/` (set by
`/init-brain`), so two hooks there keep the index current without a timer:

- `post-commit` — after every commit in brain/ (skills, `/daily`, Smeagol).
- `post-merge` — after every pull; the SessionStart sync pulls with
  `--ff-only`, which fires it.

Both start `index.py --if-new-commits` **detached** (`setsid`, `nice -n 19`)
and return at once — loading the model alone takes ~20 s. `--if-new-commits`
skips the run when brain/ HEAD equals `meta.last_indexed_commit`, which every
full-scope, non-dry run records. `flock -n` on `brain/index/.reindex.lock`
keeps two runs from writing the index at once; a commit that finds the lock
taken is simply skipped, and the next run picks its files up anyway, since
the sync is incremental by content hash. No debounce — a burst of commits
means a few short runs; add one only if that turns out to hurt.

Output goes to `brain/index/reindex.log` (gitignored with the rest of
`index/`). If the venv is missing, the hook does nothing.

## Models and chunkers

Production is configured in `.claude/gandalf.env` — the file the post-commit
hook runs with — not in code:

```
BILBO_EMBED_MODEL=granite-311m
BILBO_CHUNKER=v2
BILBO_CHUNK_PARAMS={"skip_lines": "^> (Source|Source URL|CIK|...)"}
```

Precedence: CLI flag (`--model`, `--chunker`, `--chunk-params`) > environment
variable > `gandalf.env` > built-in default (MiniLM + v1). Changing any of the
three needs one `index.py --rebuild`; the index refuses to mix models or
chunkers otherwise.

- **Models** — `MODEL_REGISTRY` in `imladris-rag/imladris/models.py`: `minilm`, `e5-small`,
  `granite-97m`, `granite-311m`, `arctic-m`, each pinned to a Hub commit, with
  the query/passage prefixes it was trained with. The query prefix,
  `trust_remote_code` and config overrides are recorded in `meta`, so Samwise
  encodes queries the same way. Chosen on 2026-09-24 by the phase-B bake-off
  (IMPLEMENTATION.md Step 9): `granite-311m`; `granite-97m` is the lighter
  fallback. `arctic-m` does not run under transformers 5 (its own 2024
  modeling code produces invalid position ids) — kept in the registry only
  as a record.
- **float32 is forced.** transformers 5 keeps a checkpoint's saved dtype, and
  granite ships bf16 weights; the Pi 5's Cortex-A76 has no bf16 support, so
  every matmul fell back to a path ~150× slower (a 30-hour build instead of
  4 minutes).
- **Chunker v2 knobs** (`DEFAULT_CHUNK_PARAMS` in `imladris/chunking.py`): `prefix` (title+path | path
  | title | none), `target` tokens, `merge_tiny`, `skip_lines`. The ablation
  on 2026-09-24 kept title+path (every lighter prefix lost 2–18 MRR points),
  256 tokens, no merging, and a boilerplate-line filter — see
  IMPLEMENTATION.md Step 9 for the numbers.

Full rebuild on the Pi: ~18 min for granite-311m (~2.4 GB peak RSS);
incremental runs from the hook touch only changed files.

## Enrichment

`BILBO_ENRICHMENT_USE=doc` (production since 2026-09-25) gives every file a
document-level vector built from an LLM summary, topics and keywords;
Samwise's `--context` uses it to rank lead files (`file_rank="zmax"`).
Before embedding, each run sends every changed file to `claude -p` (Haiku,
the subscription the CLI is logged in with, ~10 s per file, 4 in parallel)
and caches the answer in `brain/index/enrichment.db` by path + content hash
+ prompt version. A rebuild, or a model or chunker change, never re-asks.
`--enrich` fills the cache alone, without embedding (~25 min for all of
brain/ from empty). `context` is the other use, measured and not
recommended (IMPLEMENTATION.md Step 9, phase D).

- The hook needs `claude` on the `PATH` git runs with. A failed call is
  logged (`N failed`) and the file is indexed without its document vector.
  It gets one on its next change or on `--rebuild`.
- Changing `BILBO_ENRICHMENT_USE` needs one `--rebuild`, because the use is
  recorded in `meta`. An empty value makes no LLM calls at all.

## Model pinning

Every model is pinned to a fixed **HF Hub commit revision**, not the moving
`main` branch — see `MODEL_REGISTRY` in `imladris-rag/imladris/models.py`. This means:

- A re-download on a new machine, or after `--rebuild`, always fetches the
  *exact same weights* — no risk of an upstream model update silently
  changing vectors and desyncing old vs. newly-computed embeddings.
- The `(model_name, revision)` actually used is recorded in the index's
  `meta` table. If you run with a different model/revision without
  `--rebuild`, the script refuses and tells you to `--rebuild` — mixing
  vector spaces from different model versions would silently corrupt
  similarity search rather than error loudly.
- To deliberately migrate models: set `BILBO_EMBED_REVISION` (and/or
  `--model`), then run `--rebuild`.

`requirements.txt` pins `sentence-transformers` and `numpy` exactly for the
same reason (reproducible encode-time behavior). `torch` is left unpinned —
it's a transitive dependency, and hard-pinning it risks an unresolvable
conflict with sentence-transformers' own version bounds.

## Not yet done (see IMPLEMENTATION.md / the plan this was built from)

- The rest of enrichment (heuristic headers, late chunking) and a reranker —
  Index v2 phases D–E (IMPLEMENTATION.md Step 9). The truncation problem of chunker v1 (41% of
  chunks over MiniLM's 128-token window) is gone with v2 + granite's 32K
  window.
- No privacy gate — the index includes `core/`/`current/` content today, same
  as the rest of the MVP's documented privacy exception.

The reader is no longer outstanding — see `.claude/scripts/samwise/README.md`
for how Samwise queries this index, including its own known limitation
(a fixed similarity threshold under-recalls broad, many-document queries).
