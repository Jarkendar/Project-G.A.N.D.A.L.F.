"""Imladris — a small, CPU-friendly retrieval engine for markdown corpora.

Modules: `models` (pinned embedding models), `chunking` (markdown chunkers),
`corpus` (what to index), `store` (the index contract), `qdrant_store` (the
Qdrant index), `indexer` (incremental sync), `search` (semantic / keyword /
hybrid retrieval), `context` (token-budgeted bundles). It knows nothing about
any particular corpus: callers pass paths and rules in.
"""

__version__ = "0.1.0"
