#!/usr/bin/env python3
"""Print a cached source as one line per paragraph, for reading before
writing its digest. pdftotext -layout keeps hard line breaks and column
padding; this joins paragraphs and squeezes financial tables into a single
`[TABLE]` line so they cost few tokens.

Usage: reflow.py <persona> <source_id>
"""

import re
import sys

from common import source_text


def reflow(text: str) -> str:
    out = []
    for para in re.split(r"\n\s*\n", text):
        lines = para.split("\n")
        tabular = sum(1 for l in lines if re.search(r"\.{4,}|\s{6,}\S", l.strip()))
        if len(lines) > 2 and tabular > len(lines) / 2:
            rows = (re.sub(r"\s{2,}", " ", l.strip()) for l in lines if l.strip())
            out.append("[TABLE] " + " / ".join(rows)[:600])
        else:
            out.append(re.sub(r"\s+", " ", para).strip())
    return "\n".join(o for o in out if o)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(reflow(source_text(sys.argv[1], sys.argv[2])))
