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

from dataclasses import dataclass

import numpy as np

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


def _load_doc(st, path: str) -> _Doc:
    return _Doc(*st.document(path))


def _section_text(section) -> str:
    _, heading, _, _, text = section
    return f"{heading}\n\n{text}" if heading else text


FILE_RANKS = ("blocks", "zmax")


def _in_folders(path: str, folders: tuple) -> bool:
    return not folders or path.startswith(folders)


def _zscores(values: np.ndarray) -> np.ndarray:
    std = values.std()
    return (values - values.mean()) / std if std > 0 else np.zeros_like(values)


def _files_by_score(idx: Index, scores: np.ndarray, doc_scores, file_rank: str,
                    folders: tuple = ()) -> list[str]:
    """Files (under `folders`, if given) ordered by their best block, or with
    `zmax` by the better of the best block and the document vector, each
    z-scored over this query."""
    best: dict[str, float] = {}
    for i in np.argsort(-scores):
        if _in_folders(idx.paths[int(i)], folders):
            best.setdefault(idx.paths[int(i)], float(scores[i]))
    files = list(best)
    if file_rank == "zmax" and doc_scores is not None and files:
        docs = [(p, s) for p, s in zip(idx.doc_paths, doc_scores) if _in_folders(p, folders)]
        block_best = np.array([best[p] for p in files])
        z_block = dict(zip(files, _zscores(block_best).tolist()))
        z_doc = dict(zip([p for p, _ in docs], _zscores(np.array([s for _, s in docs])).tolist()))
        files.sort(key=lambda p: -max(z_block[p], z_doc.get(p, -np.inf)))
    return files


def build_context(idx: Index, query: str, count, budget: int = 1500, lead_files: int = 3,
                  pool: int = 20, section_max: int = 400, doc_max: int = 800,
                  links: bool = True, link_delta: float = 0.03, file_rank: str = "blocks",
                  reranker=None, extra_queries=(), folders=()) -> list[ContextItem]:
    """A token-budgeted context bundle for `query`. `count` counts tokens
    (the model's tokenizer). Needs a schema-2 index.

    `file_rank` orders the candidate files: "blocks" by their best block;
    "zmax", with document-level vectors (an enriched index), by the better
    of the two z-scored per query — a file's best block is a max over many
    blocks and would otherwise outscore its single document vector.

    `reranker` (an imladris.rerank.Reranker) reorders the top `pool` blocks
    before anything else; files are then ranked by their best reranked
    block and `file_rank` is ignored.

    `extra_queries` are sub-queries of a question about several things (a
    category, a group, "all X"), split by the caller. Every block is scored by
    its best match over the question and the sub-queries, and the top file of
    each sub-query joins the lead files, so every part of the question gets a
    place in the bundle.

    `folders` (path prefixes, e.g. "knowledge/projects/") keeps only files
    under them — for a question whose answer is a category the caller can
    place in the corpus tree. No file there: an empty bundle."""
    if file_rank not in FILE_RANKS:
        raise ValueError(f"unknown file_rank: {file_rank!r}")
    if idx.ids[0] is None:
        raise ValueError("context building needs a schema-2 index (rebuild it)")
    query_vecs = [embed_query(idx, q) for q in (query, *extra_queries)]
    per_query = [idx.vectors @ v for v in query_vecs]
    scores = np.max(per_query, axis=0)
    has_docs = file_rank == "zmax" and idx.doc_vectors is not None
    per_query_docs = [idx.doc_vectors @ v for v in query_vecs] if has_docs else [None] * len(query_vecs)
    folders = tuple(folders)
    order = [int(i) for i in np.argsort(-scores) if _in_folders(idx.paths[int(i)], folders)]
    if not order:
        return []
    top_score = float(scores[order[0]])
    if reranker is not None:
        head = order[:pool]
        rr = reranker.score(query, [idx.texts[i] for i in head])
        order = [head[j] for j in np.argsort(-rr, kind="stable")] + order[pool:]

    best_block: dict[str, int] = {}
    for i in order:
        best_block.setdefault(idx.paths[i], i)
    if reranker is not None:
        files_ranked = list(best_block)
    else:
        fused_docs = np.max(per_query_docs, axis=0) if has_docs else None
        files_ranked = _files_by_score(idx, scores, fused_docs, file_rank, folders)
    leads = [(p, "hit") for p in files_ranked[:lead_files]]
    for sub_scores, sub_docs in zip(per_query[1:], per_query_docs[1:]):
        top = _files_by_score(idx, sub_scores, sub_docs, file_rank, folders)[0]
        if all(top != p for p, _ in leads):
            leads.append((top, "hit"))

    docs: dict[str, _Doc] = {}

    def doc_of(path):
        if path not in docs:
            docs[path] = _load_doc(idx.store, path)
        return docs[path]

    reasons = {p: r for p, r in leads}
    if links:
        for src, _ in list(leads):
            for n in sorted(idx.store.neighbours(src), key=lambda p: -float(scores[best_block[p]])
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
    return items
