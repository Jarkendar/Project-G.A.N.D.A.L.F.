# imladris-rag

A small retrieval engine for markdown corpora, built to run on a CPU-only
board — developed and measured on a Raspberry Pi 5 (8 GB). Named after
Imladris, Elrond's house of lore.

It is corpus-agnostic: callers hand it a directory and exclusion rules, a
model and chunker choice, and a path for the index. Inside G.A.N.D.A.L.F. the
callers are two thin adapters — B.I.L.B.O. (`.claude/scripts/bilbo/index.py`,
writes the index) and S.A.M.W.I.S.E. (`.claude/scripts/samwise/search.py`,
reads it) — which add everything specific to the `brain/` knowledge base.
The package is meant to move to its own repository later without changes.

## Modules

| Module | What it does |
|---|---|
| `imladris.models` | Registry of embedding models, each pinned to a Hub commit, with the query/passage prefixes it was trained with. Loads in float32 with a capped sequence length. |
| `imladris.links` | Links between documents — markdown links, wikilinks, bare path mentions — resolved against the corpus' own file list. |
| `imladris.chunking` | Markdown chunkers. `v2` (production): structural blocks — paragraph, list, table — packed within one section up to a token budget, tables split by rows with the header repeated, each chunk prefixed with the document title and heading path. `v1`: heading + ~90-word windows, kept for comparison. |
| `imladris.corpus` | What to index: a root, a glob, exclusion rules, and a privacy rule (callable) so a caller can impose folder-level privacy. |
| `imladris.store` | SQLite index, schema 2: `documents` (hash, title, frontmatter, privacy, supersession), `nodes` — a `doc → section → block` tree with heading paths, section numbers and line ranges, blocks carrying the vectors — and `links`; a `meta` table records how the index was built and the store refuses to mix models, chunkers or schemas. |
| `imladris.indexer` | Incremental sync by content hash: only changed files are re-chunked and re-embedded, and the model is not even loaded on a no-op run. |
| `imladris.context` | Context bundles: ranked blocks widened along the document tree (section, whole document) and the link graph, within a token budget, each passage carrying path, section, line range, privacy and reason. |
| `imladris.search` | Semantic (cosine over normalized vectors), full-text (SQLite FTS5 / BM25 over blocks, prefix-stemmed queries), keyword baseline, weighted Reciprocal Rank Fusion hybrids, and per-file diversification. |

## Minimal use

```python
from pathlib import Path
from imladris import indexer, search, store
from imladris.corpus import Corpus
from imladris.models import resolve_model

corpus = Corpus(root=Path("notes"), exclude_names=frozenset({"README.md"}))
conn = store.open_store(Path("notes.db"))
indexer.sync(conn, corpus, resolve_model("granite-311m"), chunker="v2")

idx = search.load_index(Path("notes.db"))
for hit in search.semantic_search(idx, "what did I plan for Q3?", top_k=5, min_score=-1):
    print(hit["score"], hit["path"], hit["heading"])
```

Context bundle instead of ranked hits:

```python
from imladris.context import build_context
from imladris.models import load_model, token_counter

bundle = build_context(idx, "what did I plan for Q3?", token_counter(load_model(idx.spec)), budget=1500)
for item in bundle:
    print(item.path, item.section_no, item.lines, item.kind, item.tokens)
```

## Measured on a Raspberry Pi 5

Against a private 63-query golden set over a ~275-file personal knowledge
base (PL/EN), the production configuration — `granite-311m` + chunker `v2` —
scores hit@1 0.76, hit@5 0.89, MRR 0.82, up from 0.60 / 0.81 / 0.69 for the
MiniLM + `v1` baseline. A 1500-token context bundle holds the answer for
95% of queries and the right section for 92% (top-5 chunks: 84% / 85%). A full index build takes ~18 minutes; a query ~0.3 s;
peak memory ~2.4 GB. The bake-off, the chunking ablation and two traps worth
knowing (bf16 checkpoints are ~150× slower on this CPU; `arctic-m-v2.0`'s
bundled code does not run under transformers 5) are recorded in
G.A.N.D.A.L.F.'s `IMPLEMENTATION.md`, Step 9.

## Tests

```bash
python -m unittest discover imladris-rag/tests
```

The chunker and corpus tests need no model.

## Roadmap

LLM enrichment (summaries, keywords, a context line per section) and a
reranker — Index v2 phases D–E.
