"""Shared paths and helpers for the persona build scripts.

A persona lives in two places:
- brain/knowledge/personas/<slug>/  — card, catalogue, digests (git)
- ~/.local/share/gandalf/personas/<slug>/  — local cache, outside git:
    catalog.json   one row per source (id, url, wayback, sha256, words, and
                   for digested sources: file, title, source_type,
                   source_date, tags)
    originals/     files as fetched
    text/<id>.txt  plain text (pdftotext -layout / HTML without tags)
"""

import json
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
CACHE_ROOT = Path.home() / ".local/share/gandalf/personas"


def brain_path() -> Path:
    """BRAIN_PATH from .claude/gandalf.env, resolved against the project root."""
    env = PROJECT_DIR / ".claude" / "gandalf.env"
    for line in env.read_text().splitlines():
        if line.startswith("BRAIN_PATH="):
            path = Path(line.split("=", 1)[1].strip())
            path = path if path.is_absolute() else (PROJECT_DIR / path).resolve()
            if not path.is_dir():
                sys.exit(f"personas: BRAIN_PATH does not exist: {path}")
            return path
    sys.exit("personas: BRAIN_PATH not set in .claude/gandalf.env")


def persona_dir(slug: str) -> Path:
    return brain_path() / "knowledge" / "personas" / slug


def cache_dir(slug: str) -> Path:
    return CACHE_ROOT / slug


def source_text(slug: str, source_id: str) -> str:
    return (cache_dir(slug) / "text" / f"{source_id}.txt").read_text()


def catalog(slug: str) -> dict:
    rows = json.loads((cache_dir(slug) / "catalog.json").read_text())
    return {r["id"]: r for r in rows}


def norm(s: str) -> str:
    """Normalise for verbatim comparison: quotes, dashes, soft hyphens,
    hyphenation at line breaks, whitespace, case."""
    for a, b in [("’", "'"), ("‘", "'"), ("“", "'"), ("”", "'"), ('"', "'"),
                 ("–", "-"), ("—", "-"), ("›", "¢"), ("\xad", "")]:
        s = s.replace(a, b)
    s = re.sub(r"\s*-\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def missing_quotes(digest: str, source: str) -> tuple[int, list[str]]:
    """Check every `> ` blockquote in a digest against the source text.
    Quotes may be elided with `...`; each fragment must appear verbatim.
    Returns (number of quotes, fragments not found)."""
    src = norm(source)
    quotes = re.findall(r"^> (.*(?:\n> .*)*)", digest, re.M)
    missing = []
    for q in quotes:
        core = norm(re.sub(r"\n> ", " ", q)).strip(" '().")
        for frag in (f.strip(" '().,") for f in core.split("...")):
            if frag and frag not in src:
                missing.append(frag)
    return len(quotes), missing
