"""Markdown chunkers. Pure functions: text in, (heading, text-to-embed) out.

v1 — heading + ~90-word windows; kept for reference and for comparing runs.
v2 — structural: paragraph, list and table blocks packed within one section,
     never split mid-block unless a single block is over the window; budgets
     counted with the model's tokenizer; each chunk carries the document title
     and full heading path.
"""

import re
from dataclasses import dataclass
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
# Works on (line_number, text) pairs so every section and chunk knows which
# lines of the file it came from — the hierarchy and citations need that.

@dataclass
class Section:
    path: list[str]      # enclosing headings, first H1 excluded, e.g. ["Portfolio", "XTB"]
    number: str          # position among its siblings, e.g. "2.3"; "" for the preamble
    line_start: int      # 1-based, inclusive; the heading line itself for a headed section
    line_end: int
    text: str            # body text (after skip_lines), stripped
    headed: bool = True  # False for the preamble before the first heading


@dataclass
class Chunk:
    heading: str         # heading path joined with " > " (merged chunks: " | "), or the title
    text: str            # what gets embedded: prefix + body
    section: int         # index into Document.sections of the (first) section it belongs to
    line_start: int
    line_end: int


@dataclass
class Document:
    title: str
    frontmatter: dict
    sections: list[Section]
    chunks: list[Chunk]


def _numbered_body(text: str) -> tuple[dict, list[tuple[int, str]]]:
    """Frontmatter plus the body as (1-based line number, line) pairs."""
    fm, body = split_frontmatter(text)
    first = len(text[:len(text) - len(body)].splitlines()) + 1 if body is not text else 1
    return fm, list(enumerate(body.splitlines(), start=first))


def split_sections(body: str) -> list[tuple[list[str], str]]:
    """Split body into (heading_path, section_text) — heading_path is the full
    stack of enclosing headings, e.g. ["Portfolio", "XTB"]. The document's
    first H1 is left out: it restates the title, which every chunk carries
    anyway."""
    return [(s.path, s.text) for s in _sections(list(enumerate(body.splitlines(), 1)))]


def _sections(lines: list[tuple[int, str]]) -> list[Section]:
    stack: list[tuple[int, str]] = []
    counters: list[int] = []  # sibling counters per heading depth in the stack
    raw: list[tuple[list[str], str, int, list[tuple[int, str]], bool]] = [
        ([], "", lines[0][0] if lines else 1, [], False)]
    seen_heading = False
    for no, line in lines:
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            if not (level == 1 and not seen_heading):
                depth = len(stack)
                counters = counters[:depth + 1]
                if len(counters) <= depth:
                    counters.append(0)
                counters[depth] += 1
                stack.append((level, m.group(2).strip()))
            seen_heading = True
            raw.append(([h for _, h in stack], ".".join(map(str, counters[:len(stack)])), no, [], True))
        else:
            raw[-1][3].append((no, line))
    sections = []
    for path, number, start, body, headed in raw:
        if not any(l.strip() for _, l in body):
            continue
        end = max(no for no, l in body if l.strip())
        sections.append(Section(path, number, start, end, "\n".join(l for _, l in body).strip(), headed))
    return sections


def _blocks(lines: list[tuple[int, str]]) -> list[tuple[str, int, int]]:
    """Blank-line separated blocks as (text, first line, last line)."""
    blocks, current = [], []
    for no, line in lines:
        if line.strip():
            current.append((no, line))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return [("\n".join(l for _, l in b).strip(), b[0][0], b[-1][0]) for b in blocks]


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


def parse_markdown(rel_path: Path, text: str, count, params: dict | None = None) -> Document:
    """Sections and chunks of one file, with line ranges. `count` returns a
    token count under the model being indexed; `params` overrides
    DEFAULT_CHUNK_PARAMS. A piece of an oversized block keeps the whole
    block's line range."""
    params = {**DEFAULT_CHUNK_PARAMS, **(params or {})}
    fm, lines = _numbered_body(text)
    title = fm.get("title") or rel_path.stem
    if params["skip_lines"]:
        skip = re.compile(params["skip_lines"])
        lines = [(no, l) for no, l in lines if not skip.search(l)]

    def prefix_for(heading: str) -> str:
        mode = params["prefix"]
        if mode == "none":
            return ""
        if mode == "title" or not heading:
            return f"{title}\n\n" if mode != "path" or not heading else f"{heading}\n\n"
        if mode == "path":
            return f"{heading}\n\n"
        return f"{title}\n{heading}\n\n"

    sections = _sections(lines)
    if not sections and lines:
        body = "\n".join(l for _, l in lines).strip()
        sections = [Section([], "", lines[0][0], lines[-1][0], body, False)] if body else []

    # (heading, body, section index, first line, last line) before prefixing
    pieces: list[tuple[str, str, int, int, int]] = []
    for si, section in enumerate(sections):
        heading = " > ".join(h for h in section.path if h != title)
        prefix_tokens = count(prefix_for(heading))
        target = max(32, params["target"] - prefix_tokens)
        limit = max(32, CHUNK_MAX_TOKENS - prefix_tokens)
        section_lines = [(no, l) for no, l in lines if section.line_start <= no <= section.line_end
                         and not (section.headed and no == section.line_start)]

        blocks = []
        for block, first, last in _blocks(section_lines):
            parts = [block] if count(block) <= limit else split_oversize(block, limit, count)
            blocks.extend((part, first, last) for part in parts)

        current: list[tuple[str, int, int]] = []
        for block in blocks:
            if current and count("\n\n".join([b[0] for b in current] + [block[0]])) > target:
                pieces.append((heading, "\n\n".join(b[0] for b in current), si, current[0][1], current[-1][2]))
                current = []
            current.append(block)
        if current:
            pieces.append((heading, "\n\n".join(b[0] for b in current), si, current[0][1], current[-1][2]))

    if params["merge_tiny"]:
        merged = []
        carry = None  # a tiny piece waiting for a following neighbour
        for heading, body, si, first, last in pieces:
            if carry:
                heading = " | ".join(h for h in (carry[0], heading) if h)
                body, si, first = f"{carry[1]}\n\n{body}", carry[2], carry[3]
                carry = None
            if count(body) >= params["merge_tiny"]:
                merged.append((heading, body, si, first, last))
            elif merged and count(merged[-1][1] + body) <= CHUNK_MAX_TOKENS:
                ph, pb, psi, pfirst, _ = merged.pop()
                label = " | ".join(dict.fromkeys(h for h in (ph, heading) if h))
                merged.append((label, f"{pb}\n\n{body}", psi, pfirst, last))
            else:
                carry = (heading, body, si, first, last)
        if carry:
            merged.append(carry)
        pieces = merged

    chunks = [Chunk(heading or title, prefix_for(heading) + body, si, first, last)
              for heading, body, si, first, last in pieces]
    return Document(title, fm, sections, chunks)


def chunk_markdown_v2(rel_path: Path, text: str, count, params: dict | None = None) -> list[tuple[str, str]]:
    """Return [(heading_path, text_to_embed), ...] — the flat view of parse_markdown."""
    return [(c.heading, c.text) for c in parse_markdown(rel_path, text, count, params).chunks]


CHUNKERS = ("v1", "v2")


def chunk_file(chunker: str, rel_path: Path, text: str, count, params: dict | None = None):
    if chunker == "v2":
        return chunk_markdown_v2(rel_path, text, count, params)
    return chunk_markdown_v1(rel_path, text)
