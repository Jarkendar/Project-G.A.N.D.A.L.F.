"""Markdown chunkers. Pure functions: text in, (heading, text-to-embed) out.

v1 — heading + ~90-word windows; kept for reference and for comparing runs.
v2 — structural: paragraph, list and table blocks packed within one section,
     never split mid-block unless a single block is over the window; budgets
     counted with the model's tokenizer; each chunk carries the document title
     and full heading path.
"""

import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+|\n+")

MAX_CHUNK_WORDS = 90  # v1: keeps chunks under a ~128-token window
CHUNK_TARGET_TOKENS = 256
CHUNK_MAX_TOKENS = 512

DEFAULT_CHUNK_PARAMS = {
    "prefix": "title+path",  # context embedded with each chunk: title+path | path | title | none
    "target": CHUNK_TARGET_TOKENS,  # pack blocks of one section up to this many tokens
    "merge_tiny": 0,         # fold chunks whose body is under this many tokens into a neighbour
    "skip_lines": "",        # regex; matching lines (boilerplate) are dropped before chunking
}


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw_fm = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in raw_fm.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"')
    return fm, body


# --- v1 ------------------------------------------------------------------------

def split_by_heading(body: str) -> list[tuple[str, str]]:
    """Split body into (heading, section_text) blocks. Text before the first
    heading (if any) gets heading '' (preamble)."""
    blocks: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            if current_lines and any(l.strip() for l in current_lines):
                blocks.append((current_heading, current_lines))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and any(l.strip() for l in current_lines):
        blocks.append((current_heading, current_lines))
    return [(h, "\n".join(ls).strip()) for h, ls in blocks]


def split_into_windows(text: str, max_words: int) -> list[str]:
    """Split text into paragraph-aligned windows of at most max_words words.
    A single paragraph longer than max_words is hard-split by word count."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    windows: list[str] = []
    current: list[str] = []
    current_words = 0
    for para in paragraphs:
        para_words = para.split()
        if len(para_words) > max_words:
            if current:
                windows.append("\n\n".join(current))
                current, current_words = [], 0
            for i in range(0, len(para_words), max_words):
                windows.append(" ".join(para_words[i:i + max_words]))
            continue
        if current_words + len(para_words) > max_words and current:
            windows.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(para)
        current_words += len(para_words)
    if current:
        windows.append("\n\n".join(current))
    return windows


def chunk_markdown_v1(rel_path: Path, text: str) -> list[tuple[str, str]]:
    """Return [(heading, chunk_text_with_context), ...] for one file."""
    fm, body = split_frontmatter(text)
    title = fm.get("title") or rel_path.stem
    blocks = split_by_heading(body) or [("", body.strip())]
    chunks: list[tuple[str, str]] = []
    for heading, section_text in blocks:
        if not section_text:
            continue
        for window in split_into_windows(section_text, MAX_CHUNK_WORDS):
            display_heading = heading or title
            embed_text = f"{title}\n{display_heading}\n\n{window}" if heading else f"{title}\n\n{window}"
            chunks.append((display_heading, embed_text))
    return chunks


# --- v2 ------------------------------------------------------------------------

def split_sections(body: str) -> list[tuple[list[str], str]]:
    """Split body into (heading_path, section_text) — heading_path is the full
    stack of enclosing headings, e.g. ["Portfolio", "XTB"]. The document's
    first H1 is left out: it restates the title, which every chunk carries
    anyway."""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[list[str], list[str]]] = [([], [])]
    seen_heading = False
    for line in body.splitlines():
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            if not (level == 1 and not seen_heading):
                stack.append((level, m.group(2).strip()))
            seen_heading = True
            sections.append(([h for _, h in stack], []))
        else:
            sections[-1][1].append(line)
    return [(path, "\n".join(lines).strip()) for path, lines in sections
            if any(l.strip() for l in lines)]


def split_oversize(block: str, budget: int, count) -> list[str]:
    """Split one block that exceeds the window: a table by row groups with the
    header repeated, anything else by sentences. A single sentence still over
    budget is cut by words as a last resort."""
    lines = block.splitlines()
    if len(lines) > 2 and all(l.lstrip().startswith("|") for l in lines):
        header, rows = lines[:2], lines[2:]
        pieces, current = [], []
        for row in rows:
            if current and count("\n".join(header + current + [row])) > budget:
                pieces.append("\n".join(header + current))
                current = []
            current.append(row)
        if current:
            pieces.append("\n".join(header + current))
        return pieces
    pieces, current = [], ""
    for sentence in (x for x in SENTENCE_END_RE.split(block) if x.strip()):
        candidate = f"{current} {sentence}".strip()
        if current and count(candidate) > budget:
            pieces.append(current)
            candidate = sentence
        current = candidate
    if current:
        pieces.append(current)
    out = []
    for piece in pieces:
        if count(piece) <= budget:
            out.append(piece)
            continue
        words = piece.split()
        step = max(1, len(words) * budget // count(piece))
        out.extend(" ".join(words[i:i + step]) for i in range(0, len(words), step))
    return out


def chunk_markdown_v2(rel_path: Path, text: str, count, params: dict | None = None) -> list[tuple[str, str]]:
    """Return [(heading_path, text_to_embed), ...]. `count` returns a token
    count under the model being indexed; `params` overrides
    DEFAULT_CHUNK_PARAMS."""
    params = {**DEFAULT_CHUNK_PARAMS, **(params or {})}
    fm, body = split_frontmatter(text)
    title = fm.get("title") or rel_path.stem
    if params["skip_lines"]:
        skip = re.compile(params["skip_lines"])
        body = "\n".join(l for l in body.splitlines() if not skip.search(l))

    def prefix_for(heading: str) -> str:
        mode = params["prefix"]
        if mode == "none":
            return ""
        if mode == "title" or not heading:
            return f"{title}\n\n" if mode != "path" or not heading else f"{heading}\n\n"
        if mode == "path":
            return f"{heading}\n\n"
        return f"{title}\n{heading}\n\n"

    pieces: list[tuple[str, str]] = []  # (heading, body) before prefixing
    for path, section_text in split_sections(body) or [([], body.strip())]:
        heading = " > ".join(h for h in path if h != title)
        prefix_tokens = count(prefix_for(heading))
        target = max(32, params["target"] - prefix_tokens)
        limit = max(32, CHUNK_MAX_TOKENS - prefix_tokens)

        blocks = []
        for block in (b.strip() for b in re.split(r"\n\s*\n", section_text)):
            if not block:
                continue
            blocks.extend([block] if count(block) <= limit else split_oversize(block, limit, count))

        current: list[str] = []
        for block in blocks:
            if current and count("\n\n".join(current + [block])) > target:
                pieces.append((heading, "\n\n".join(current)))
                current = []
            current.append(block)
        if current:
            pieces.append((heading, "\n\n".join(current)))

    if params["merge_tiny"]:
        merged: list[tuple[str, str]] = []
        carry: tuple[str, str] | None = None  # a tiny piece waiting for a following neighbour
        for heading, text_ in pieces:
            if carry:
                heading = " | ".join(h for h in (carry[0], heading) if h)
                text_ = f"{carry[1]}\n\n{text_}"
                carry = None
            if count(text_) >= params["merge_tiny"]:
                merged.append((heading, text_))
            elif merged and count(merged[-1][1] + text_) <= CHUNK_MAX_TOKENS:
                prev_heading, prev_text = merged.pop()
                label = " | ".join(dict.fromkeys(h for h in (prev_heading, heading) if h))
                merged.append((label, f"{prev_text}\n\n{text_}"))
            else:
                carry = (heading, text_)
        if carry:
            merged.append(carry)
        pieces = merged

    return [(heading or title, prefix_for(heading) + text_) for heading, text_ in pieces]


CHUNKERS = ("v1", "v2")


def chunk_file(chunker: str, rel_path: Path, text: str, count, params: dict | None = None):
    if chunker == "v2":
        return chunk_markdown_v2(rel_path, text, count, params)
    return chunk_markdown_v1(rel_path, text)
