"""A corpus: a directory of markdown files plus the rules for what to leave out.
The engine knows nothing else about where the files come from."""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


def default_privacy(rel_path: Path, frontmatter: dict) -> str:
    """The document's own `privacy:` field, private when it has none."""
    return frontmatter.get("privacy") or "private"


@dataclass(frozen=True)
class Corpus:
    root: Path
    pattern: str = "*.md"
    exclude_top_dirs: frozenset = field(default_factory=frozenset)   # first path part, e.g. "index"
    exclude_prefixes: tuple = ()                                      # posix prefixes, e.g. "logs/raw"
    exclude_names: frozenset = field(default_factory=frozenset)      # file names, e.g. "CLAUDE.md"
    # (relative path, frontmatter) -> "private" | "public"; callers encode
    # their own rules here (e.g. folder-level privacy that overrides the file)
    privacy_of: Callable[[Path, dict], str] = default_privacy

    def is_excluded(self, rel_path: Path) -> bool:
        if rel_path.parts and rel_path.parts[0] in self.exclude_top_dirs:
            return True
        posix = rel_path.as_posix()
        if any(posix.startswith(prefix) for prefix in self.exclude_prefixes):
            return True
        return rel_path.name in self.exclude_names

    def discover(self, scope: Path | None = None) -> list[Path]:
        """Relative paths of indexable files, sorted; `scope` narrows the walk
        to one file or subdirectory of the root."""
        start = scope if scope is not None else self.root
        candidates = [start] if start.is_file() else start.rglob(self.pattern)
        found = []
        for p in candidates:
            if not p.is_file():
                continue
            rel = p.relative_to(self.root)
            if not self.is_excluded(rel):
                found.append(rel)
        return sorted(found, key=lambda r: r.as_posix())


def file_hash(abs_path: Path) -> str:
    return hashlib.sha256(abs_path.read_bytes()).hexdigest()
