#!/usr/bin/env python3
"""Step 3b: check that every quote in a persona's digests appears verbatim
in the cached source text. Exits 1 if any quote is missing.

Usage: verify_quotes.py <persona> [source_id ...]
  No ids: every digest already written in brain/knowledge/personas/<persona>/sources/.
"""

import sys

from common import catalog, missing_quotes, persona_dir, source_text


def main(slug: str, ids: list[str]) -> int:
    cat = catalog(slug)
    ids = ids or [i for i, r in cat.items()
                  if "file" in r and (persona_dir(slug) / "sources" / r["file"]).exists()]
    total = bad = 0
    for i in ids:
        digest = (persona_dir(slug) / "sources" / cat[i]["file"]).read_text()
        n, missing = missing_quotes(digest, source_text(slug, i))
        total += n
        bad += len(missing)
        for frag in missing:
            print(f"{i} MISSING: {frag[:140]}")
    print(f"digests {len(ids)}, quotes {total}, missing {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
