"""Document enrichment: an LLM reads each file once and returns a summary,
bilingual topic categories, search keywords, and one context sentence per
section. Retrieval then has what chunks alone lack — the category a note
belongs to even when the note never names it ("side project", "cycling
race"), and what each section is about within its document.

Results are cached per (path, content hash, prompt version) in a database
of their own — not in the index, whose model, chunker and variants may
change and be rebuilt without ever re-asking the LLM. An unchanged file is
never sent again. Providers are swappable; the one
shipped runs the Claude Code CLI headless (`claude -p`), so it uses the
subscription the CLI is logged in with, not an API key.
"""

import json
import sqlite3
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .chunking import parse_markdown
from .corpus import Corpus, file_hash

PROMPT_VERSION = "1"

SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "topics": {"type": "array", "items": {"type": "string"}},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "sections": {"type": "array", "items": {
            "type": "object",
            "properties": {"number": {"type": "string"}, "context": {"type": "string"}},
            "required": ["number", "context"]}},
    },
    "required": ["summary", "topics", "keywords", "sections"],
}

PROMPT = """You annotate one note from a personal knowledge base (Polish and English) so that a search engine can find it.
Return JSON only, following the schema.

- summary: 2-3 sentences on what the note is and what it contains, in the note's own language.
- topics: 3-6 general categories this note belongs to, each given in English AND Polish (e.g. "side project / projekt poboczny", "cycling race / wyścig kolarski", "restaurant / restauracja"). Name the category even when the note never uses that word.
- keywords: 8-15 specific terms someone might search with (names, places, products, concepts), mixing Polish and English forms.
- sections: for every section listed below, one sentence situating it within the note (what it covers, why it matters), in the note's language. Use the section numbers as given ("0" is the text before the first heading).

Note path: {path}
Title: {title}
Sections (number: heading path):
{sections}

Note:
<<<
{text}
>>>"""


def build_prompt(rel_path: Path, text: str) -> str:
    doc = parse_markdown(rel_path, text, lambda t: len(t.split()))
    sections = "\n".join(f"- {s.number or '0'}: {' > '.join(s.path) or '(preamble)'}" for s in doc.sections)
    return PROMPT.format(path=rel_path.as_posix(), title=doc.title, sections=sections or "- 0: (whole note)",
                         text=text)


class EnrichmentError(Exception):
    pass


@dataclass
class ClaudeCliEnricher:
    """`claude -p` with no tools and no MCP servers (a headless run that loads
    the user's MCP plugins would compete with the interactive session for
    them), from an empty working directory so no project hooks fire."""
    model: str = "haiku"
    timeout: int = 300
    cli: str = "claude"

    @property
    def name(self) -> str:
        return f"claude-cli:{self.model}"

    def __call__(self, prompt: str) -> dict:
        with tempfile.TemporaryDirectory() as cwd:
            proc = subprocess.run(
                [self.cli, "-p", "--model", self.model, "--tools", "", "--strict-mcp-config",
                 "--output-format", "json", "--json-schema", json.dumps(SCHEMA)],
                input=prompt, capture_output=True, text=True, timeout=self.timeout, cwd=cwd)
        if proc.returncode != 0:
            raise EnrichmentError(f"exit {proc.returncode}: {proc.stderr.strip()[:300]}")
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise EnrichmentError(str(envelope.get("result"))[:300])
        data = envelope.get("structured_output") or json.loads(envelope["result"])
        missing = [k for k in SCHEMA["required"] if k not in data]
        if missing:
            raise EnrichmentError(f"missing fields {missing}")
        return data


CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrichment (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    provider TEXT NOT NULL,
    data TEXT NOT NULL,                 -- JSON: summary, topics, keywords, sections
    created_at TEXT NOT NULL
);
"""


def open_cache(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(CACHE_SCHEMA)
    return conn


def stored(conn: sqlite3.Connection) -> dict:
    """path -> (content_hash, prompt_version) of cached enrichments."""
    return {p: (h, v) for p, h, v in conn.execute("SELECT path, content_hash, prompt_version FROM enrichment")}


def load(conn: sqlite3.Connection) -> dict:
    """path -> enrichment dict, for every cached file."""
    return {p: json.loads(d) for p, d in conn.execute("SELECT path, data FROM enrichment")}


def enrich_corpus(conn: sqlite3.Connection, corpus: Corpus, enricher, workers: int = 4,
                  scope: Path | None = None, retries: int = 2, log=print) -> dict:
    """Enrich every file whose content or the prompt changed since its cached
    enrichment. Calls run in parallel; results are written as they arrive,
    so an interrupted run keeps what it finished. Returns counts."""
    cached = stored(conn)
    todo = []
    for rel in corpus.discover(scope):
        h = file_hash(corpus.root / rel)
        if cached.get(rel.as_posix()) != (h, PROMPT_VERSION):
            todo.append((rel, h))
    counts = {"enriched": 0, "cached": len(corpus.discover(scope)) - len(todo), "failed": 0}
    if not todo:
        return counts
    log(f"enriching {len(todo)} file(s) with {enricher.name}, {workers} at a time ...")

    def work(rel: Path, h: str):
        prompt = build_prompt(rel, (corpus.root / rel).read_text(encoding="utf-8", errors="replace"))
        for attempt in range(retries + 1):
            try:
                return rel, h, enricher(prompt), None
            except (EnrichmentError, subprocess.TimeoutExpired, json.JSONDecodeError, KeyError) as err:
                if attempt == retries:
                    return rel, h, None, err
                time.sleep(10 * (attempt + 1))

    start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, rel, h) for rel, h in todo]
        for n, future in enumerate(as_completed(futures), 1):
            rel, h, data, err = future.result()
            if err is not None:
                counts["failed"] += 1
                log(f"[{n}/{len(todo)}] FAILED {rel}: {err}")
                continue
            conn.execute(
                "INSERT INTO enrichment(path, content_hash, prompt_version, provider, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET content_hash=excluded.content_hash, "
                "prompt_version=excluded.prompt_version, provider=excluded.provider, data=excluded.data, "
                "created_at=excluded.created_at",
                (rel.as_posix(), h, PROMPT_VERSION, enricher.name, json.dumps(data, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat(timespec="seconds")))
            conn.commit()
            counts["enriched"] += 1
            log(f"[{n}/{len(todo)}] {rel} ({time.time() - start:.0f}s)")
    return counts
