"""Context building: turn ranked blocks into a bundle of passages that fits a
token budget, widening each hit along the document tree and the link graph.

Order — the best block of each of the top `lead_files` files first (so the
bundle never collapses onto one file), then every other hit block in score
order, as a plain top-k would. Each hit is widened before it is added:
  hits in two or more sections of a short document -> the whole document;
  a hit in a short section -> the whole section;
  otherwise the bare hit block.
A section (or document) already in the bundle is not added twice; an item
over the remaining budget falls back to the bare block, else is skipped.

Links — documents linked to or from the lead files whose own best block
scores within `link_delta` of the query's top score are added as lead files
too: a neighbour is followed only when it is relevant to the question.
"""

import sqlite3
from dataclasses import dataclass

import numpy as np

from . import store
from .search import Index, embed_query


@dataclass
class ContextItem:
    path: str
    title: str
    privacy: str
    kind: str          # "document" | "section" | "blocks"
    heading: str
    section_no: str | None
    lines: tuple | None
    text: str
    score: float       # best block score of this file
    reason: str        # "hit" | "link from <path>"
    tokens: int


@dataclass
class _Doc:
    title: str
    privacy: str
    sections: dict     # section node id -> (section_no, heading, line_start, line_end, text)
    blocks: list       # (node id, section node id, text, line_start, line_end), in file order


def _load_doc(conn: sqlite3.Connection, path: str) -> _Doc:
    title, privacy = conn.execute("SELECT title, privacy FROM documents WHERE path = ?", (path,)).fetchone()
    sections = {row[0]: row[1:] for row in conn.execute(
        "SELECT id, section_no, heading, line_start, line_end, text FROM nodes "
        "WHERE path = ? AND level = 'section' ORDER BY ord", (path,))}
    blocks = conn.execute(
        "SELECT id, parent_id, text, line_start, line_end FROM nodes "
        "WHERE path = ? AND level = 'block' ORDER BY ord", (path,)).fetchall()
    return _Doc(title, privacy, sections, blocks)


def _neighbours(conn: sqlite3.Connection, path: str) -> set[str]:
    rows = conn.execute("SELECT dst FROM links WHERE src = ? AND dst IS NOT NULL "
                        "UNION SELECT src FROM links WHERE dst = ?", (path, path)).fetchall()
    return {r[0] for r in rows} - {path}


def _section_text(section) -> str:
    _, heading, _, _, text = section
    return f"{heading}\n\n{text}" if heading else text


def build_context(idx: Index, query: str, count, budget: int = 1500, lead_files: int = 3,
                  pool: int = 20, section_max: int = 400, doc_max: int = 800,
                  links: bool = True, link_delta: float = 0.03) -> list[ContextItem]:
    """A token-budgeted context bundle for `query`. `count` counts tokens
    (the model's tokenizer). Needs a schema-2 index."""
    if idx.ids[0] is None:
        raise ValueError("context building needs a schema-2 index (rebuild it)")
    scores = idx.vectors @ embed_query(idx, query)
    order = [int(i) for i in np.argsort(-scores)]
    top_score = float(scores[order[0]])

    best_block: dict[str, int] = {}
    for i in order:
        best_block.setdefault(idx.paths[i], i)
    files_ranked = list(best_block)
    leads = [(p, "hit") for p in files_ranked[:lead_files]]

    conn = store.open_readonly(idx.db_path)
    docs: dict[str, _Doc] = {}
    try:
        def doc_of(path):
            if path not in docs:
                docs[path] = _load_doc(conn, path)
            return docs[path]

        reasons = {p: r for p, r in leads}
        if links:
            for src, _ in list(leads):
                for n in sorted(_neighbours(conn, src), key=lambda p: -float(scores[best_block[p]])
                                if p in best_block else 1):
                    if n not in reasons and n in best_block and float(scores[best_block[n]]) >= top_score - link_delta:
                        leads.append((n, f"link from {src}"))
                        reasons[n] = f"link from {src}"

        # hit blocks to widen: lead files' best blocks, then the rest by score
        queue = [best_block[p] for p, _ in leads]
        queue += [i for i in order[:pool] if i not in queue]

        items, used = [], 0
        covered: set = set()          # section node ids, or ("doc", path)
        hit_sections: dict[str, set] = {}
        for i in order[:pool]:
            path = idx.paths[i]
            hit_sections.setdefault(path, set()).add(dict((b[0], b[1]) for b in doc_of(path).blocks)[idx.ids[i]])

        for i in queue:
            path, node_id = idx.paths[i], idx.ids[i]
            doc = doc_of(path)
            if ("doc", path) in covered:
                continue
            section_id = next(b[1] for b in doc.blocks if b[0] == node_id)
            if section_id in covered:
                continue
            block = next(b for b in doc.blocks if b[0] == node_id)
            sec = doc.sections.get(section_id)
            candidates = []
            if len(hit_sections.get(path, ())) >= 2:
                whole = "\n\n".join(_section_text(s) for s in doc.sections.values())
                candidates.append(("document", doc.title, None, None, whole, ("doc", path)))
            if sec:
                candidates.append(("section", sec[1], sec[0], (sec[2], sec[3]), _section_text(sec), section_id))
            candidates.append(("blocks", idx.headings[i], sec[0] if sec else None, (block[3], block[4]),
                               block[2], None))
            limits = {"document": doc_max, "section": section_max}
            for kind, heading, section_no, lines, text, cover in candidates:
                tokens = count(text)
                if tokens > limits.get(kind, tokens) or used + tokens > budget:
                    continue
                items.append(ContextItem(path, doc.title, doc.privacy, kind, heading, section_no, lines, text,
                                         round(float(scores[i]), 4), reasons.get(path, "hit"), tokens))
                used += tokens
                if cover:
                    covered.add(cover)
                break
    finally:
        conn.close()
    return items
