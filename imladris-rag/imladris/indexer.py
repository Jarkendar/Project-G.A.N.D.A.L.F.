"""Incremental indexing: compare the corpus with the store by content hash,
parse, chunk and embed only what changed, drop what disappeared, and keep
the link graph resolved against the current set of files."""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import store
from .chunking import DEFAULT_CHUNK_PARAMS, chunk_markdown_v1, parse_markdown, split_frontmatter
from .corpus import Corpus, file_hash
from .links import Resolver, extract_links
from .models import ModelSpec, load_model, token_counter


@dataclass
class SyncResult:
    updated: int = 0
    chunks: int = 0
    deleted: int = 0
    unchanged: int = 0
    links: int = 0


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


def _parse(chunker: str, rel: Path, content: str, count, chunk_params: dict | None):
    """(title, frontmatter, sections, chunks) as plain dicts for the store."""
    if chunker == "v2":
        doc = parse_markdown(rel, content, count, chunk_params)
        sections = [{"heading": " > ".join(h for h in s.path if h != doc.title) or doc.title,
                     "section_no": s.number, "line_start": s.line_start, "line_end": s.line_end,
                     "text": s.text} for s in doc.sections]
        chunks = [{"heading": c.heading, "text": c.text, "section": c.section,
                   "line_start": c.line_start, "line_end": c.line_end} for c in doc.chunks]
        return doc.title, doc.frontmatter, sections, chunks
    frontmatter, _ = split_frontmatter(content)
    title = frontmatter.get("title") or rel.stem
    chunks = [{"heading": h, "text": t, "section": None, "line_start": None, "line_end": None}
              for h, t in chunk_markdown_v1(rel, content)]
    return title, frontmatter, [], chunks


def relink(conn: sqlite3.Connection, resolver: Resolver) -> int:
    """Re-resolve every stored link against the current file set; returns how
    many links resolve to a document in the corpus."""
    rows = conn.execute("SELECT rowid, src, raw, kind FROM links").fetchall()
    for rowid, src, raw, kind in rows:
        target = {"markdown": resolver.markdown, "wikilink": resolver.wikilink}.get(
            kind, lambda _src, r: resolver.path(r))(src, raw)
        conn.execute("UPDATE links SET dst = ? WHERE rowid = ?", (target, rowid))
    return conn.execute("SELECT COUNT(*) FROM links WHERE dst IS NOT NULL").fetchone()[0]


ENRICHMENT_USES = ("doc", "context")


def doc_embed_text(title: str, data: dict) -> str:
    """What a document-level vector encodes: title, topics, keywords, summary."""
    return "\n".join([title, "; ".join(data.get("topics", [])), ", ".join(data.get("keywords", [])),
                      data.get("summary", "")])


def sync(conn: sqlite3.Connection, corpus: Corpus, spec: ModelSpec, chunker: str = "v1",
         chunk_params: dict | None = None, scope: Path | None = None, rebuild: bool = False,
         log=print, enrichment: dict | None = None, use: tuple = ()) -> SyncResult:
    """Bring the store in line with the corpus. Raises store.IndexMismatch if
    the store was built with another schema, model, chunker or enrichment use
    and `rebuild` is off.

    `enrichment` maps paths to enrich.py results; `use` picks how they feed
    the vectors: "doc" adds a document-level vector (title, topics, keywords,
    summary), "context" prepends each block's section context sentence to
    what gets embedded (the stored block text stays the note's own)."""
    if unknown := set(chunk_params or {}) - set(DEFAULT_CHUNK_PARAMS):
        raise ValueError(f"unknown chunk params: {sorted(unknown)}")
    if unknown := set(use) - set(ENRICHMENT_USES):
        raise ValueError(f"unknown enrichment uses: {sorted(unknown)}")
    use_key = ",".join(sorted(use))
    if rebuild:
        store.reset(conn)
    else:
        store.check_consistency(conn, spec.name, spec.revision, chunker)
        built_with = store.get_meta(conn).get("enrichment_use")
        if built_with is not None and built_with != use_key:
            raise store.IndexMismatch(f"index was built with enrichment use '{built_with}', this run "
                                      f"requests '{use_key}'. Run with --rebuild.")
    enrichment = enrichment or {}

    to_update, to_delete, unchanged = plan(conn, corpus, scope, rebuild)
    result = SyncResult(unchanged=unchanged)
    resolver = Resolver({p.as_posix() for p in corpus.discover()})

    if to_update:
        # Loaded only when there is something to embed: a no-op run stays instant.
        log(f"loading {spec.name}@{spec.revision} ...")
        model = load_model(spec)
        count = token_counter(model)

        parsed = {}
        texts = []
        for rel in to_update:
            content = (corpus.root / rel).read_text(encoding="utf-8", errors="replace")
            parsed[rel] = (content, *_parse(chunker, rel, content, count, chunk_params))
            title, _, sections, chunks = parsed[rel][1:]
            data = enrichment.get(rel.as_posix())
            context_by_no = {c["number"]: c["context"] for c in (data or {}).get("sections", [])}
            for chunk in chunks:
                chunk["embed_text"] = chunk["text"]
                if "context" in use and chunk["section"] is not None:
                    number = sections[chunk["section"]]["section_no"] or "0"
                    if context_by_no.get(number):
                        chunk["embed_text"] = f"{context_by_no[number]}\n{chunk['text']}"
                texts.append(chunk["embed_text"])
            if "doc" in use and data:
                texts.append(doc_embed_text(title, data))

        vectors = []
        if texts:
            log(f"embedding {len(texts)} texts from {len(to_update)} file(s) ...")
            vectors = model.encode([spec.passage_prefix + t for t in texts],
                                   batch_size=16 if chunker == "v2" else 32,
                                   normalize_embeddings=True, show_progress_bar=True)

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = 0
        for rel in to_update:
            content, title, frontmatter, sections, chunks = parsed[rel]
            for chunk, vec in zip(chunks, vectors[cursor:cursor + len(chunks)]):
                chunk["vector"] = vec.astype("float32").tobytes()
                chunk["token_count"] = count(chunk["text"]) if chunker == "v2" else len(chunk["text"].split())
            cursor += len(chunks)
            posix = rel.as_posix()
            doc_vector, doc_text = None, None
            if "doc" in use and enrichment.get(posix):
                doc_text = doc_embed_text(title, enrichment[posix])
                doc_vector = vectors[cursor].astype("float32").tobytes()
                cursor += 1
            links = [{"dst": l.target, "raw": l.raw, "kind": l.kind, "line": l.line}
                     for l in extract_links(posix, content, resolver)]
            abs_path = corpus.root / rel
            store.write_document(conn, posix, content_hash=file_hash(abs_path),
                                 mtime=abs_path.stat().st_mtime, indexed_at=now, title=title,
                                 frontmatter=frontmatter, privacy=corpus.privacy_of(rel, frontmatter),
                                 sections=sections, blocks=chunks, links=links,
                                 doc_text=doc_text, doc_vector=doc_vector)
            result.updated += 1
            result.chunks += len(chunks)

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
            enrichment_use=use_key,
        )

    for path in to_delete:
        store.delete_document(conn, path)
        result.deleted += 1
    if to_update or to_delete:
        result.links = relink(conn, resolver)
    conn.commit()
    return result
