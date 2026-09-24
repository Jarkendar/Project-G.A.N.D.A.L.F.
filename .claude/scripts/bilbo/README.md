# B.I.L.B.O. — Bot Indexing Local Binary Objects

The indexer. Per README.md: *"Not a reactive agent — runs in the background as
a scheduled task. Walks watched directories, detects new or modified files,
chunks them, and stores them in the knowledge base."*

Bilbo **writes** the embedding index. It never answers a query — that's
**S.A.M.W.I.S.E.**'s job (`.claude/scripts/samwise/search.py` +
`.claude/agents/samwise.md`): encode the query with the same pinned model,
rank `brain/` chunks by cosine similarity against `chunks.vector`, and return
ranked paths + snippets for Claude to `Read` deeper. Bilbo builds the index;
Samwise reads it. Neither role crosses into the other.

## What it does

1. Walks `brain/` for `*.md` files, excluding `current/smeagol/` (Smeagol's
   logs — not knowledge), `index/` (its own output), and every per-folder
   `CLAUDE.md` (operating instructions, not retrievable knowledge).
2. Hashes each file's content and compares against the last-indexed hash
   stored in `brain/index/bilbo.db`. **Unchanged files are skipped entirely —
   zero re-embedding cost.** Only new/changed files get (re)chunked and
   (re)embedded; deleted files have their chunks removed.
3. Chunks each file by markdown heading, sub-splitting further so no chunk
   exceeds ~90 words — comfortably under this model's ~128-token window
   (going over means silent truncation, not an error, which would quietly
   degrade retrieval quality).
4. Embeds all changed chunks in one batched `model.encode(...)` call
   (normalized vectors, so cosine similarity = dot product at query time).
5. Upserts everything into `brain/index/bilbo.db` (SQLite — outside
   `brain/db/`, which is G.I.M.L.I.'s access monopoly per `brain/db/CLAUDE.md`).

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

## Model pinning

The model (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) is
pinned to a fixed **HF Hub commit revision**, not the moving `main` branch —
see `DEFAULT_MODEL_REVISION` in `index.py`. This means:

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

- **Chunks are truncated, measured: `MAX_CHUNK_WORDS = 90` does not bound
  token count.** On the real `brain/` (2026-09-22, 1756 chunks), 713 chunks
  (41%) exceed the model's 128-token window and ~19% of all tokens are
  silently dropped before embedding. Polish text runs ~1.5–2 tokens per word,
  and table-heavy sections are far worse — a 49-word chunk of one table
  tokenized to 323. Chunking v2 (token-based limits, table-aware splitting)
  is a planned step.
- No privacy gate — the index includes `core/`/`current/` content today, same
  as the rest of the MVP's documented privacy exception.

The reader is no longer outstanding — see `.claude/scripts/samwise/README.md`
for how Samwise queries this index, including its own known limitation
(a fixed similarity threshold under-recalls broad, many-document queries).
