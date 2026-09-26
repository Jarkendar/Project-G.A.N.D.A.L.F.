# S.A.M.W.I.S.E. — SQL And Markdown Wading Into Semantic Embeddings

The reader. B.I.L.B.O. (`.claude/scripts/bilbo/index.py`) **writes** the
embedding index at `brain/index/bilbo.db`; Samwise only **reads** it — encodes
a query with the exact `(model, revision)` pair recorded in the index's `meta`
table, cosine-ranks chunks against it, and returns ranked paths + scores +
snippets. Bilbo builds the index; Samwise reads it. Neither role crosses into
the other — `search.py` opens the database via a `mode=ro` URI connection and
never writes to `brain/index/`.
Retrieval itself is `imladris.search` from the `imladris-rag/` package at
the repo root; `search.py` is the brain/ adapter (paths, corpus rules,
threshold, CLI).

This directory holds the query engine (`search.py`), the MCP server Gandalf
queries it through (`mcp_server.py`) and the eval harness (`eval/`). There is
no sub-agent: Gandalf calls the tools directly and does the judging and
reading itself (`.claude/skills/gandalf/SKILL.md`, Step 2d).

## MCP server

`mcp_server.py` serves the same retrieval as two read-only tools, registered
as `samwise` in the repo's `.mcp.json`:

| tool | = CLI | returns |
|---|---|---|
| `context(query, budget, follow_links, rerank)` | `--context --format text` | a cited, token-budgeted bundle of passages |
| `search(query, strategy, top_k, min_score, diversify, wide, rerank)` | ranked mode, `--format text` | score, path, section, snippet per hit |

`wide=True` is the broad-question preset (top 20, no threshold, one block per
file). The tool descriptions carry the usage guidance and measured numbers —
they are what the calling model reads.

**One shared process over HTTP.** Production runs it as a systemd user
service, `samwise-mcp.service` (in this directory, linked into
`~/.config/systemd/user/`), on `http://127.0.0.1:8765/mcp`, stateless — so
every Claude Code session shares one copy of the model, and a restart does
not break clients. `--transport stdio` (the default when run by hand) gives
one process per client.

```bash
systemctl --user enable --now "$PWD/.claude/scripts/samwise/samwise-mcp.service"
systemctl --user restart samwise-mcp   # after changing the server code
```

**RAM.** The MCP server is ~80 MB and never imports torch; the model and the
index live in a worker process started by the first query (~14 s) and kept
for later ones (~0.3–0.5 s). Measured on the Pi 5:

| state | RSS |
|---|---|
| idle, no worker | ~95 MB |
| worker loaded (granite-311m float32 = 1.6 GB of it) | ~2.2 GB |

After `SAMWISE_IDLE_UNLOAD` seconds without a query (default 600, 0 = never)
the worker is shut down. A separate process because an in-process unload
gave back only ~0.4 GB of the 2.2 — torch keeps the rest, whatever glibc's
malloc tunables say. If the worker dies (e.g. killed for RAM), the call
reports it and the next one starts a new worker.

**Never stale.** Before each call the worker fingerprints the index's
per-file content hashes (~10 ms on Qdrant) and reloads when B.I.L.B.O. has
changed anything since.

**Index down** (Qdrant not running): the tools return `SAMWISE: index
unavailable — …` with the fix; **service down**: the `samwise` tools are
missing from the session. Either way Gandalf falls back to grep.

`mcp==2.2.0` lives in Bilbo's venv (`.claude/scripts/bilbo/requirements.txt`).

## What it does

`search.py` supports three strategies, sharing one code path so the same
script backs both the live agent and the eval:

- **`semantic`** (default) — encode the query, rank all chunks by cosine
  similarity (vectors are pre-normalized, so cosine == dot product), return
  the top-k above `--min-score`.
- **`grep`** — keyword baseline: extract non-stopword tokens from the query
  (case-preserving so acronyms like `CV`/`AI` survive at 2 characters),
  count occurrences per file, rank by count. This is what Gandalf did before
  Samwise existed, kept as the fallback path and the eval's comparison point.
- **`hybrid`** — Reciprocal Rank Fusion (k=60) of the two rankings above.
  **Measured to underperform pure semantic on this corpus** — see below.

## Running it

Samwise has no separate Python environment — it shares Bilbo's `.venv` rather
than installing `sentence-transformers`/`torch` twice:

```bash
.claude/scripts/bilbo/.venv/bin/python .claude/scripts/samwise/search.py \
  "what do I know about X" --strategy semantic --top-k 8
```

```bash
--strategy {semantic,grep,hybrid}   # default: semantic
--top-k N                           # default: 8
--min-score F                       # default: 0.845 (set per model, see below)
--format {json,text}                # default: json
```

Also usable as a module (the eval harness does this to load the model once
for the whole run instead of once per subprocess):

```python
import search
idx = search.load_index(brain_dir)
results = search.semantic_search(idx, "query", top_k=8, min_score=search.DEFAULT_MIN_SCORE)
```

## Calibration: `eval/`

The golden set — 63 hand-labeled PL/EN queries since 2026-09-24 (20 until
then), each tagged with a `type` (point, multi, cross-lingual, deep, table,
link, entity) and optionally the expected section and an answer snippet —
approved before measuring — lives
**in brain/, not here**: `brain/_meta/eval/samwise-golden.jsonl`. Each entry
pairs a real question with the real file that answers it, so the set
describes brain/'s contents and has no place in a public repo. `run_eval.py`
resolves it through `BRAIN_PATH`; `SAMWISE_GOLDEN` overrides the location
(absolute, or relative to brain/). `eval/golden.example.jsonl` documents the
format with synthetic entries and is never used for measuring.

`eval/run_eval.py` runs all three strategies in-process against it and
reports hit@1/3/5, MRR, precision@5, recall@5, full-recall@5, a per-query
"who picked what" table, and an F1-optimal cosine threshold swept over the
score distribution of correct vs. incorrect semantic hits:

```bash
cd .claude/scripts/samwise/eval
../../bilbo/.venv/bin/python run_eval.py
```

Since 2026-09-24 (Index v2, phase A) it also reports section_hit@5 (an
expected file's chunk under an expected heading), answer@5 (the answer
snippet appears in the top-5 chunk text), ctx_chars@5, hit@5 / MRR per query
type, query latency p50/p95 and peak RSS. Options:

```bash
# evaluate an experimental index built with: ../../bilbo/index.py --db <path>
run_eval.py --index ../../../../../brain/index/exp/<variant>.db
# subset of strategies, no per-query listing, results kept for comparison
run_eval.py --strategies semantic,hybrid --quiet \
    --json-out ../../../../../brain/index/eval-runs/<date>_<variant>.json
```

Keep `--json-out` files in `brain/index/eval-runs/` (gitignored with the rest
of `brain/index/`): they contain the private queries.

**Result (2026-07-03):** semantic wins outright (hit@1 0.70 vs. grep's 0.40
and hybrid's 0.60; MRR 0.75 vs. 0.50 / 0.70) and is the default strategy.
Hybrid underperforms pure semantic — RRF folds in enough of grep's false
positives (especially Polish queries against English-language notes, where
literal keyword matching fails outright) to drag it down rather than help.
F1-optimal threshold **0.5047** (precision 0.665, recall 0.791) was wired into
`search.py`'s `DEFAULT_MIN_SCORE`. Full numbers: `IMPLEMENTATION.md` Step 3.

**Since 2026-09-24 (Index v2, phase B):** the production index runs
granite-311m with chunker v2 — semantic hit@1 0.76, MRR 0.82 on the 63-query
set (MiniLM: 0.60 / 0.69). The threshold is recalibrated to **0.8684**
(precision 0.552, recall 0.775): cosine scores are model-specific, so the old
value means nothing for the new model. On 2026-09-26 it was lowered to
**0.845** in favour of recall — on the 83-query set, no empty results and
77/83 queries with a relevant hit, versus 3 empty and 69/83 at 0.8684. Semantic still beats hybrid. Samwise
applies the index's recorded query prefix, `trust_remote_code` and config
overrides from its `meta` table, and loads the model in float32. Full
numbers: `IMPLEMENTATION.md` Step 9.

### Known limitation — not solved by threshold tuning

Two of the five multi-file golden-set queries — both broad, category-shaped
ones expecting three documents each — scored **0/3 expected files in the
top-5 across all three strategies, even fully ungated** (`--min-score 0.0`).
Per-chunk embeddings favor literal vocabulary overlap over topical
relatedness: a category noun that recurs across unrelated documents buries
the handful of files that actually belong to that category. No fixed score
cutoff fixes this; the two-file multi-hit queries worked fine, so the failure
mode is specific to broad, many-document, low-lexical-overlap categories, not
multi-file queries generally.

The mitigation lives in the agent's workflow (`.claude/agents/samwise.md`),
not in the retrieval math: Samwise judges whether a question is a point
lookup or a broad/enumerative one, and for the latter widens `--top-k`/
`--min-score` and applies its own relevance judgment over the wider candidate
list instead of trusting a clean cutoff.

## Access boundary

Samwise (paired with Bilbo as writer) is the sole reader of
`brain/index/bilbo.db`. G.I.M.L.I. is the sole reader of `brain/db/*.db` — a
separate world; Gimli never touches `brain/index/`, and Samwise never runs
`sqlite3` against `brain/db/`. The system grows in depth (new, narrow,
per-domain monopolies), not breadth (one monopoly expanding to cover more
ground).
