#!/usr/bin/env python3
"""Write persona digest drafts with Antigravity CLI (`agy`), one headless call
per source, in parallel. A drop-in for the manual draft step: the output is
`<drafts>/<id>.md` in the format assemble.py reads (see
.claude/skills/persona/references/digest.md), so quotes are still checked by
`assemble.py <persona> <drafts> <ids>` without --write.

The model gets the source text inside the prompt and no tools at all:
agy runs from an empty temp dir and every tool action is denied in
~/.gemini/antigravity-cli/settings.json. Raw JSON envelopes (usage, status)
land in `<drafts>/_agy/<id>.json`.

Usage: agy_digest.py <persona> <drafts_dir> <id>[,<id>...]
           [--model gemini-3.8-flash-low] [--jobs 4] [--timeout 600]
           [--surname Jaroszek]
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from common import PROJECT_DIR, catalog, source_text
from reflow import reflow

SCHEMA = Path(__file__).with_name("agy_digest.schema.json")
RULES = PROJECT_DIR / ".claude/skills/persona/references/digest.md"
ARGV_LIMIT = 120_000  # Linux MAX_ARG_STRLEN is 131072 bytes per argument
RETRIES = 3  # attempts per source when the model returns 429

HEAD = """You write one persona digest (Polish "esencja") of ONE source. The
digest is the evidence layer for a later "persona card": what this source shows
about how the person thinks and decides. Write in Polish.

Hard rules:
- Use ONLY the source text below. No web search, no outside knowledge, no tools.
- Read the whole source; it is an automatic transcript or an article (typos and
  ASR errors are possible, and there may be no speaker labels).
- "quotes": 0-2 lines copied VERBATIM from the source, in its language, only
  the person's own words and only where the line is the crux of the reasoning.
  Copy character for character; if unsure, return an empty list.
- "change": you see only this one source. Write "Brak porównania — źródło
  digestowane osobno." unless the source itself refers to the person's earlier
  views.
- Sponsored content, approximate dates, garbled transcript: say so in
  "doubts".
- Keep what carries the argument: concrete figures, amounts, names, tickers,
  dates and examples, not just the abstract thesis. A reader of the digest
  must be able to see WHAT the person looked at and WHY they concluded it.
- "decisions": real decisions and stated views of the person (situation -> what
  they weighed -> decision), not general advice that the source merely repeats.
  Skip the section's content rather than invent a decision.
- Length: ~150-300 words for a short source (under ~3000 words), 400-800 for a
  long one. A long transcript with a short digest is a lossy digest.

The digest format and its rules (the JSON fields mirror the sections):

"""


def prompt(slug: str, row: dict, surname: str) -> str:
    meta = (
        f"SOURCE METADATA\nid: {row['id']}\ntitle: {row['title']}\n"
        f"type: {row['source_type']}\ndate: {row['source_date']}\n"
        f"person: {surname}\n\nSOURCE TEXT\n"
    )
    return HEAD + RULES.read_text() + "\n\n" + meta + reflow(source_text(slug, row["id"]))


def render(d: dict) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) or "- (brak)"

    # a blank line between quotes: consecutive `>` lines are one blockquote to the checker
    quotes = "\n\n".join(f"> {q}" for q in d["quotes"]) or "> (brak)"
    out = [
        f"tags: [{', '.join(d['tags'])}]",
        "---",
        "",
        f"# {d['heading']}",
        "",
        "## Kontekst",
        "",
        d["context"],
        "",
        "## Kluczowe tezy",
        "",
        bullets(d["theses"]),
        "",
        "## Sposób myślenia",
        "",
        bullets(d["reasoning"]),
        "",
        "## Decyzje i poglądy",
        "",
        bullets(d["decisions"]),
        "",
        "## Cytaty",
        "",
        quotes,
        "",
        "## Zmiana względem wcześniejszych lat",
        "",
        d["change"],
    ]
    if d.get("doubts"):
        out += ["", "<!-- doubts: " + d["doubts"].replace("--", "-") + " -->"]
    return "\n".join(out) + "\n"


def call_agy(cmd, timeout):
    """One agy call in an empty temp dir. Returns (envelope, stderr) or (None, why)."""
    with tempfile.TemporaryDirectory() as cwd:
        try:
            r = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=timeout + 60,
            )
        except subprocess.TimeoutExpired:
            return None, "timeout"
    try:
        return json.loads(r.stdout), r.stderr
    except json.JSONDecodeError:
        return None, (r.stderr or r.stdout)[:200]


def run_one(slug, row, drafts, model, timeout, surname):
    sid = row["id"]
    started = time.time()
    p = prompt(slug, row, surname)
    if len(p.encode()) > ARGV_LIMIT:
        return sid, "too-large", f"prompt {len(p.encode())} B > {ARGV_LIMIT}", 0.0, {}
    cmd = [
        "agy", "-p", p, "--model", model, "--output-format", "json",
        "--json-schema", str(SCHEMA), "--print-timeout", f"{timeout}s",
    ]
    env, err = None, ""
    for attempt in range(RETRIES):
        env, err = call_agy(cmd, timeout)
        failed = env is None or env.get("status") != "SUCCESS" or not env.get("structured_output")
        # 429 shows up in the envelope's error text; back off and retry only that
        if not failed or "RESOURCE_EXHAUSTED" not in json.dumps(env or err):
            break
        time.sleep(20 * (attempt + 1))
    dt = time.time() - started
    if env is None:
        return sid, "bad-envelope", err, dt, {}
    (drafts / "_agy").mkdir(exist_ok=True)
    (drafts / "_agy" / f"{sid}.json").write_text(json.dumps(env, ensure_ascii=False))
    usage = env.get("usage", {})
    data = env.get("structured_output")
    if env.get("status") != "SUCCESS" or not data:
        return sid, env.get("status", "?"), str(env.get("error") or err)[:200], dt, usage
    (drafts / f"{sid}.md").write_text(render(data))
    return sid, "ok", "", dt, usage


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("persona")
    ap.add_argument("drafts", type=Path)
    ap.add_argument("ids")
    ap.add_argument("--model", default="gemini-3.8-flash-low")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--surname", default=None)
    a = ap.parse_args()
    surname = a.surname or a.persona.title()
    a.drafts.mkdir(parents=True, exist_ok=True)
    cat = catalog(a.persona)
    rows = [cat[i] for i in a.ids.split(",") if i]
    failed = 0
    tokens = 0
    with ThreadPoolExecutor(a.jobs) as pool:
        futs = [pool.submit(run_one, a.persona, r, a.drafts, a.model, a.timeout, surname) for r in rows]
        for f in futs:
            sid, status, note, dt, usage = f.result()
            tokens += usage.get("total_tokens", 0)
            failed += status != "ok"
            print(f"{status:12} {dt:6.1f}s {usage.get('total_tokens', 0):>8} tok  {sid}  {note}")
    print(f"done {len(rows) - failed}/{len(rows)}, {tokens} tokens total")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
