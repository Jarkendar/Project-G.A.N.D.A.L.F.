"""Links between documents of a corpus: markdown links, wikilinks, and bare
path mentions. Resolved against the corpus' own file list, so a link to
something outside it (a URL, an image, a missing file) resolves to None."""

import posixpath
import re
from dataclasses import dataclass

MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
PATH_MENTION_RE = re.compile(r"(?<![\w/.\-\]\(])((?:[\w.\-]+/)+[\w.\-]+\.md)\b")


@dataclass(frozen=True)
class Link:
    raw: str            # the target as written
    kind: str           # "markdown" | "wikilink" | "path"
    line: int           # 1-based line in the source file
    target: str | None  # resolved corpus-relative path, or None


class Resolver:
    """Resolves link targets against the set of corpus paths (posix, relative)."""

    def __init__(self, paths: set[str]):
        self.paths = paths
        self.by_stem: dict[str, list[str]] = {}
        for p in paths:
            self.by_stem.setdefault(posixpath.splitext(posixpath.basename(p))[0].lower(), []).append(p)

    def markdown(self, src: str, target: str) -> str | None:
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            return None  # URL, mailto:, in-page anchor
        target = target.split("#", 1)[0]
        if not target.endswith(".md"):
            return None
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(src), target))
        return joined if joined in self.paths else self.path(target)

    def wikilink(self, src: str, slug: str) -> str | None:
        candidates = self.by_stem.get(slug.strip().lower(), [])
        if len(candidates) == 1:
            return candidates[0]
        same_dir = [c for c in candidates if posixpath.dirname(c) == posixpath.dirname(src)]
        return same_dir[0] if len(same_dir) == 1 else None

    def path(self, mention: str) -> str | None:
        """Exact corpus path, else the unique corpus path the mention ends with
        or that ends with the mention (a mention may carry the corpus root's
        own directory name as a prefix, or be written relative to a subfolder)."""
        mention = posixpath.normpath(mention.lstrip("./"))
        if mention in self.paths:
            return mention
        parts = mention.split("/")
        for i in range(1, len(parts)):
            if (tail := "/".join(parts[i:])) in self.paths:
                return tail
        suffix = [p for p in self.paths if p.endswith("/" + mention)]
        return suffix[0] if len(suffix) == 1 else None


def extract_links(src: str, text: str, resolver: Resolver) -> list[Link]:
    """All links in one file, deduplicated per (kind, raw), self-links dropped."""
    found: dict[tuple[str, str], Link] = {}
    for no, line in enumerate(text.splitlines(), start=1):
        spans = []
        for m in MD_LINK_RE.finditer(line):
            spans.append(m.span())
            found.setdefault(("markdown", m.group(1)),
                             Link(m.group(1), "markdown", no, resolver.markdown(src, m.group(1))))
        for m in WIKILINK_RE.finditer(line):
            spans.append(m.span())
            found.setdefault(("wikilink", m.group(1)),
                             Link(m.group(1), "wikilink", no, resolver.wikilink(src, m.group(1))))
        for m in PATH_MENTION_RE.finditer(line):
            if any(a <= m.start() < b for a, b in spans):
                continue  # already counted as part of a markdown link
            found.setdefault(("path", m.group(1)),
                             Link(m.group(1), "path", no, resolver.path(m.group(1))))
    return [link for link in found.values() if link.target != src]
