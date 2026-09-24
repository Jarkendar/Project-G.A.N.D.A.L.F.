"""Imladris — a small, CPU-friendly retrieval engine for markdown corpora.

Modules: `models` (pinned embedding models), `chunking` (markdown chunkers),
`corpus` (what to index), `store` (SQLite index), `indexer` (incremental
sync), `search` (semantic / keyword / hybrid retrieval). It knows nothing
about any particular corpus: callers pass paths and rules in.
"""

__version__ = "0.1.0"
