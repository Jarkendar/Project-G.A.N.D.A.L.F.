#!/usr/bin/env python3
"""Turn draft digests into finished digest files in brain/.

A draft is `<drafts>/<source_id>.md`: first line `tags: [topic, ...]`, then
`---`, then the digest body. The script checks its quotes (step 3b), adds
frontmatter from the catalog row, writes
`brain/knowledge/personas/<persona>/sources/<file>` and flips the source's
status in sources.md from `todo` to `esencja`.

Catalog row fields used: url, wayback, sha256, file, title, source_type,
source_date, tags (fixed tags placed after `persona, <persona>`).

Usage: assemble.py <persona> <drafts_dir> <id>[,<id>...] [--write] [--force]
  Without --write: quote check only. --force writes despite missing quotes.
"""

import datetime
import re
import sys
from pathlib import Path

from common import catalog, missing_quotes, persona_dir, source_text

REQUIRED = ("url", "sha256", "file", "title", "source_type", "source_date")


def frontmatter(slug: str, row: dict, topic_tags: str, now: str) -> str:
    topics = [t.strip() for t in topic_tags.split(",") if t.strip()]
    # dict.fromkeys: a draft may repeat a fixed tag (e.g. its source type)
    tags = ", ".join(dict.fromkeys(["persona", slug, *row.get("tags", []), *topics]))
    return f"""---
date: {now}
source: persona-digest
privacy: public
status: active
tags: [{tags}]
title: "{row['title']}"
persona: {slug}
source_id: "{row['id']}"
source_type: {row['source_type']}
source_date: {row['source_date']}
url: {row['url']}
wayback: {row['wayback']}
sha256: {row['sha256']}
digest_lang: pl
"""


def main(slug: str, drafts: Path, ids: list[str], write: bool, force: bool) -> int:
    cat = catalog(slug)
    total = bad = 0
    for i in ids:
        n, missing = missing_quotes((drafts / f"{i}.md").read_text(), source_text(slug, i))
        total += n
        bad += len(missing)
        for frag in missing:
            print(f"{i} MISSING: {frag[:140]}")
    print(f"quotes {total}, missing {bad}")
    if bad and not force:
        return 1
    if not write:
        return 0

    gaps = {i: [k for k in REQUIRED if not cat[i].get(k)] for i in ids}
    if any(gaps.values()):
        # `wayback` may legitimately be pending; everything else must be filled.
        print("catalog.json rows missing fields:", {i: g for i, g in gaps.items() if g})
        return 1

    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    base = persona_dir(slug)
    catalogue = base / "sources.md"
    s = catalogue.read_text()
    for i in ids:
        row = cat[i]
        tags_line, body = (drafts / f"{i}.md").read_text().split("\n", 1)
        topic_tags = tags_line.split("[", 1)[1].rstrip("]")
        (base / "sources" / row["file"]).write_text(frontmatter(slug, row, topic_tags, now) + body)
        s = re.sub(rf"^(\| {re.escape(i)} \|.*?\|) todo \|", r"\1 esencja |", s, flags=re.M)
        print(f"{i} -> sources/{row['file']}")
    s = re.sub(r"^updated: .*$", "updated: " + now, s, count=1, flags=re.M)
    catalogue.write_text(s)
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 3:
        sys.exit(__doc__)
    sys.exit(main(args[0], Path(args[1]), args[2].split(","),
                  "--write" in sys.argv, "--force" in sys.argv))
