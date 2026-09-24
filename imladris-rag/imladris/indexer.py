"""Incremental indexing: compare the corpus with the store by content hash,
chunk and embed only what changed, drop what disappeared."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .chunking import DEFAULT_CHUNK_PARAMS, chunk_file
from .corpus import Corpus, file_hash
from .models import ModelSpec, load_model, token_counter


@dataclass
class SyncResult:
    updated: int = 0
    chunks: int = 0
    deleted: int = 0
    unchanged: int = 0


def plan(conn: sqlite3.Connection, corpus: Corpus, scope: Path | None, rebuild: bool):
    """(files to (re)index, stored paths to delete, unchanged count)."""
    disk_files = corpus.discover(scope)
    disk_set = {p.as_posix() for p in disk_files}
    existing = {} if rebuild else store.stored_hashes(conn)

    to_update, unchanged = [], 0
    for rel in disk_files:
        if existing.get(rel.as_posix()) == file_hash(corpus.root / rel):
            unchanged += 1
        else:
            to_update.append(rel)

    scope_prefix = None
    if scope is not None and scope != corpus.root:
        scope_prefix = scope.relative_to(corpus.root).as_posix()
    to_delete = [p for p in existing
                 if p not in disk_set and not (scope_prefix and not p.startswith(scope_prefix))]
    return to_update, to_delete, unchanged


def sync(conn: sqlite3.Connection, corpus: Corpus, spec: ModelSpec, chunker: str = "v1",
         chunk_params: dict | None = None, scope: Path | None = None, rebuild: bool = False,
         log=print) -> SyncResult:
    """Bring the store in line with the corpus. Raises store.IndexMismatch if
    the store was built with another model or chunker and `rebuild` is off."""
    if unknown := set(chunk_params or {}) - set(DEFAULT_CHUNK_PARAMS):
        raise ValueError(f"unknown chunk params: {sorted(unknown)}")
    if rebuild:
        store.reset(conn)
    else:
        store.check_consistency(conn, spec.name, spec.revision, chunker)

    to_update, to_delete, unchanged = plan(conn, corpus, scope, rebuild)
    result = SyncResult(unchanged=unchanged)

    if to_update:
        # Loaded only when there is something to embed: a no-op run stays instant.
        log(f"loading {spec.name}@{spec.revision} ...")
        model = load_model(spec)
        count = token_counter(model)

        per_file = {}
        texts = []
        for rel in to_update:
            content = (corpus.root / rel).read_text(encoding="utf-8", errors="replace")
            per_file[rel] = chunk_file(chunker, rel, content, count, chunk_params)
            texts.extend(text for _, text in per_file[rel])

        vectors = []
        if texts:
            log(f"embedding {len(texts)} chunks from {len(to_update)} file(s) ...")
            vectors = model.encode([spec.passage_prefix + t for t in texts],
                                   batch_size=16 if chunker == "v2" else 32,
                                   normalize_embeddings=True, show_progress_bar=True)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = 0
        for rel in to_update:
            chunks = per_file[rel]
            file_vectors = vectors[cursor:cursor + len(chunks)]
            cursor += len(chunks)
            rows = [(heading, text, vec.astype("float32").tobytes(),
                     count(text) if chunker == "v2" else len(text.split()))
                    for (heading, text), vec in zip(chunks, file_vectors)]
            abs_path = corpus.root / rel
            store.replace_file(conn, rel.as_posix(), file_hash(abs_path),
                               abs_path.stat().st_mtime, now, rows)
            result.updated += 1
            result.chunks += len(rows)

        store.set_meta(
            conn,
            model_name=spec.name,
            model_revision=spec.revision,
            embed_dim=str(model.get_sentence_embedding_dimension()),
            schema_version=store.SCHEMA_VERSION,
            chunker=chunker,
            query_prefix=spec.query_prefix,
            trust_remote_code="1" if spec.trust_remote_code else "0",
            config_kwargs=json.dumps(spec.config_kwargs or {}),
            chunk_params=json.dumps({**DEFAULT_CHUNK_PARAMS, **(chunk_params or {})}
                                    if chunker == "v2" else {}, sort_keys=True),
        )

    for path in to_delete:
        store.delete_file(conn, path)
        result.deleted += 1
    conn.commit()
    return result
