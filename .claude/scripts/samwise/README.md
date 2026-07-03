# S.A.M.W.I.S.E. — SQL And Markdown Wading Into Semantic Embeddings

The reader. B.I.L.B.O. (`.claude/scripts/bilbo/index.py`) **writes** the
embedding index at `brain/index/bilbo.db`; Samwise only **reads** it — encodes
a query with the exact `(model, revision)` pair recorded in the index's `meta`
table, cosine-ranks chunks against it, and returns ranked paths + scores +
snippets. Bilbo builds the index; Samwise reads it. Neither role crosses into
the other — `search.py` opens the database via a `mode=ro` URI connection and
never writes to `brain/index/`.

The conversational sub-agent lives at `.claude/agents/samwise.md`; this
directory holds the underlying query engine (`search.py`) and its eval
harness (`eval/`).

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
--min-score F                       # default: 0.5047 (calibrated, see below)
--format {json,text}                # default: json
```

Also usable as a module (the eval harness does this to load the model once
for the whole run instead of once per subprocess):

```python
import search
idx = search.load_index(brain_dir)
results = search.semantic_search(idx, "query", top_k=8, min_score=0.5047)
```

## Calibration: `eval/`

`eval/golden.jsonl` — 20 hand-labeled PL/EN queries (15 single-file point
lookups + 5 genuinely multi-file topical queries), approved before measuring.
`eval/run_eval.py` runs all three strategies in-process against it and
reports hit@1/3/5, MRR, precision@5, recall@5, full-recall@5, a per-query
"who picked what" table, and an F1-optimal cosine threshold swept over the
score distribution of correct vs. incorrect semantic hits:

```bash
cd .claude/scripts/samwise/eval
../../bilbo/.venv/bin/python run_eval.py
```

**Result (2026-07-03):** semantic wins outright (hit@1 0.70 vs. grep's 0.40
and hybrid's 0.60; MRR 0.75 vs. 0.50 / 0.70) and is the default strategy.
Hybrid underperforms pure semantic — RRF folds in enough of grep's false
positives (especially Polish queries against English-language notes, where
literal keyword matching fails outright) to drag it down rather than help.
F1-optimal threshold **0.5047** (precision 0.665, recall 0.791) is wired into
`search.py`'s `DEFAULT_MIN_SCORE`. Full numbers: `IMPLEMENTATION.md` Step 3.

### Known limitation — not solved by threshold tuning

Two of the five multi-file golden-set queries ("what are my side-projects",
"what cycling trips have I done") scored **0/3 expected files in the top-5
across all three strategies, even fully ungated** (`--min-score 0.0`).
Per-chunk embeddings favor literal vocabulary overlap over topical
relatedness — e.g. "projekt" is heavily overloaded by career/job documents in
this corpus, burying the actual `knowledge/projects/` files for a plural,
category-shaped query. No fixed score cutoff fixes this; a two-file multi-hit
query (Capgemini contract + benefits) worked fine, so the failure mode is
specific to broad, many-document, low-lexical-overlap categories, not
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
