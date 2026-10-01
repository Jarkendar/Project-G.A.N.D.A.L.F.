#!/usr/bin/env python3
"""Step 2: build a persona's local source cache and catalog.json from a
source list.

The source list (`<cache>/<slug>/sources.json`, or a path given with
--sources) is a JSON array written by hand while scoping the persona:

    [{"id": "1990-06-the-route-to-performance",
      "url": "https://.../memo.pdf",
      "title": "...", "source_type": "memo", "source_date": "1990-06-01",
      "tags": ["memo"]}, ...]

Only `id` and `url` are required; the other fields are copied into the
catalog row (assemble.py needs title, source_type, source_date and file
later). For each source this script downloads the original into
`originals/<id>.<ext>` (skipped when present, unless --refetch), extracts
plain text into `text/<id>.txt` (PDF: `pdftotext -layout`, or reading
order with `"layout": false` for multi-column scans; HTML: tags dropped,
layout kept), and records sha256 and word count. --wayback looks
up an existing Wayback Machine snapshot; it never asks the archive to save
a page (Save Page Now is an outbound write — only with the owner's yes, by
hand). --table prints rows for the persona's sources.md.

A source with `"from": "<parent id>"` and `"start": "<regex>"` is an
excerpt: a part of another source's file (e.g. one memo in a collection
of memos). The regex (multiline) marks where it starts, searched after the
previous excerpt of the same parent; it runs to the next one. Its text is
written to `text/<id>.txt`; url, sha256 and wayback are the parent's, plus
the page range. A parent marked `"collection": true` is left out of
--table. The source list lives in the persona's brain/ folder
(`knowledge/personas/<slug>/sources.json`) when it carries anything a
script cannot re-derive — such as these anchors.

Usage: fetch.py <persona> [--sources FILE] [--only id,...] [--refetch]
                          [--wayback] [--table] [--batch-size N]
"""

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import urllib.parse
from html.parser import HTMLParser

from common import cache_dir, persona_dir

USER_AGENT = "Mozilla/5.0 (X11; Linux aarch64) gandalf-persona-fetch/1.0"
BLOCK_TAGS = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
              "pre", "title", "table", "blockquote", "hr"}


class _Text(HTMLParser):
    """HTML to text: drops script/style, keeps text as laid out (letters in
    <pre> keep their line breaks), a newline around block elements."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def decode(raw: bytes) -> str:
    """UTF-8 when it is valid, else windows-1252 — old pages (Buffett's
    1977–1997 letters) are cp1252 and declare no charset."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def html_to_text(raw: bytes) -> str:
    parser = _Text()
    parser.feed(decode(raw))
    text = html.unescape("".join(parser.out))
    return re.sub(r"\n{3,}", "\n\n", text)


def download(url: str) -> tuple[bytes, str]:
    """The body (decoded) and its Content-Type. Through curl: some sites send
    brotli even unasked (berkshirehathaway.com via Sucuri), which Python's
    standard library cannot decode."""
    proc = subprocess.run(
        ["curl", "-sSL", "--compressed", "--fail", "--max-time", "120", "-A", USER_AGENT,
         "-w", "\n%{content_type}", url],
        capture_output=True, check=False)
    if proc.returncode:
        raise OSError(f"curl exit {proc.returncode}: {proc.stderr.decode(errors='replace').strip()[:200]}")
    body, _, ctype = proc.stdout.rpartition(b"\n")
    return body, ctype.decode(errors="replace")


def extension(url: str, content_type: str, raw: bytes) -> str:
    if raw[:5] == b"%PDF-" or "pdf" in content_type:
        return "pdf"
    if "html" in content_type or url.lower().endswith((".html", ".htm")):
        return "html"
    return "txt"


def extract(path, ext: str, layout: bool = True) -> str:
    """Plain text of an original. `layout=False` drops `pdftotext -layout`:
    reading order instead of physical layout, for multi-column scans
    (journal articles, newspaper clippings) whose columns -layout
    interleaves line by line."""
    if ext == "pdf":
        return subprocess.run(["pdftotext", *(["-layout"] if layout else []), str(path), "-"],
                              capture_output=True, text=True, check=True).stdout
    raw = path.read_bytes()
    return html_to_text(raw) if ext == "html" else decode(raw)


def wayback_snapshot(url: str) -> str:
    """URL of the closest existing snapshot, or '' (never saves a page)."""
    api = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe=":/")
    for attempt in range(3):
        try:
            data, _ = download(api)
            closest = json.loads(data).get("archived_snapshots", {}).get("closest") or {}
            return closest.get("url", "") if closest.get("available") else ""
        except (OSError, json.JSONDecodeError):
            time.sleep(5 * (attempt + 1))  # the API answers 503 under load
    return ""


def table_rows(rows: list[dict], batch_size: int) -> str:
    out = []
    for n, r in enumerate(rows):
        wb = f"[wayback]({r['wayback']})" if r.get("wayback") else "— brak"
        out.append(f"| {r['id']} | {r.get('source_type', '')} | {r.get('source_date', '')} | "
                   f"{r.get('words', '')} | P{n // batch_size + 1} | todo | "
                   f"[link]({r['url']}{'#page=' + r['pages'].split('–')[0] if r.get('pages') else ''}) | "
                   f"{wb} | `{r.get('sha256', '')[:16]}` |")
    return "\n".join(out)


def excerpt_bounds(parent_text: str, excerpts: list[dict]) -> list[tuple[int, int]]:
    """(start, end) offsets of each excerpt in the parent text: each `start`
    regex (multiline) is searched after the previous match, and an excerpt
    runs to the next one's start (the last one to the end)."""
    starts, pos = [], 0
    for src in excerpts:
        m = re.compile(src["start"], re.M).search(parent_text, pos)
        if not m:
            raise ValueError(f"{src['id']}: anchor not found after offset {pos}: {src['start']}")
        starts.append(m.start())
        pos = m.end()
    return [(a, starts[i + 1] if i + 1 < len(starts) else len(parent_text)) for i, a in enumerate(starts)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("persona")
    ap.add_argument("--sources", help="source list (default: sources.json in the persona's brain/ "
                                      "folder, else in its cache)")
    ap.add_argument("--only", help="comma-separated ids to process")
    ap.add_argument("--refetch", action="store_true", help="download again even if cached")
    ap.add_argument("--wayback", action="store_true", help="look up existing Wayback snapshots")
    ap.add_argument("--table", action="store_true", help="print sources.md rows")
    ap.add_argument("--batch-size", type=int, default=10)
    args = ap.parse_args()

    base = cache_dir(args.persona)
    default = persona_dir(args.persona) / "sources.json"
    sources = json.loads(open(args.sources or (default if default.exists() else base / "sources.json")).read())
    only = set(args.only.split(",")) if args.only else None
    (base / "originals").mkdir(parents=True, exist_ok=True)
    (base / "text").mkdir(exist_ok=True)
    catalog_path = base / "catalog.json"
    catalog = {r["id"]: r for r in json.loads(catalog_path.read_text())} if catalog_path.exists() else {}
    excerpts = [src for src in sources if "from" in src]
    parents = {src["from"] for src in excerpts}

    failed = 0
    texts = {}
    for src in sources:
        sid = src["id"]
        if "from" in src or (only and sid not in only and sid not in parents):
            continue
        row = {**catalog.get(sid, {}), **src}
        cached = sorted(base.glob(f"originals/{sid}.*"))
        try:
            if cached and not args.refetch:
                path = cached[0]
                ext = path.suffix[1:]
            else:
                raw, ctype = download(src["url"])
                ext = extension(src["url"], ctype, raw)
                path = base / "originals" / f"{sid}.{ext}"
                path.write_bytes(raw)
                time.sleep(1)  # be polite to the source site
            text = extract(path, ext, src.get("layout", True))
        except (subprocess.CalledProcessError, OSError) as err:
            print(f"{sid} FAILED: {err}", file=sys.stderr)
            failed += 1
            continue
        texts[sid] = text
        (base / "text" / f"{sid}.txt").write_text(text)
        row.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), words=len(text.split()))
        if args.wayback and not row.get("wayback"):
            row["wayback"] = wayback_snapshot(src["url"])
        row.setdefault("wayback", "")
        catalog[sid] = row
        print(f"{sid}: {ext}, {row['words']} words, sha256 {row['sha256'][:16]}"
              + (f", wayback {'yes' if row['wayback'] else 'none'}" if args.wayback else ""))

    # Excerpts: sources cut out of a parent file (e.g. a collection of memos) —
    # their own id, text and page range; the parent's url, sha256 and wayback.
    for parent in sorted(parents):
        if parent not in texts:
            print(f"excerpts of {parent} skipped: parent not fetched", file=sys.stderr)
            failed += 1
            continue
        group = [src for src in excerpts if src["from"] == parent]
        try:
            bounds = excerpt_bounds(texts[parent], group)
        except ValueError as err:
            print(f"FAILED: {err}", file=sys.stderr)
            failed += 1
            continue
        prow = catalog[parent]
        for src, (a, b) in zip(group, bounds):
            if only and src["id"] not in only:
                continue
            text = texts[parent][a:b]
            first, last = texts[parent][:a].count("\f") + 1, texts[parent][:b].rstrip("\f").count("\f") + 1
            row = {**catalog.get(src["id"], {}), **src, "url": prow["url"], "sha256": prow["sha256"],
                   "wayback": prow.get("wayback", ""), "words": len(text.split()),
                   "pages": f"{first}–{last}" if last > first else str(first)}
            (base / "text" / f"{src['id']}.txt").write_text(text)
            catalog[src["id"]] = row
        print(f"{parent}: {len(group)} excerpts")

    order = [s["id"] for s in sources]
    rows = sorted(catalog.values(), key=lambda r: order.index(r["id"]) if r["id"] in order else len(order))
    catalog_path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    if args.table:
        print(table_rows([r for r in rows if r["id"] in order and not r.get("collection")], args.batch_size))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
