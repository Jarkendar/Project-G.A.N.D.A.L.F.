#!/usr/bin/env python3
# M.Í.R.D.A.I.N. tools for F.I.N.R.O.D. — the persona builder.
#
# The persona scripts (fetch.py, reflow.py, assemble.py, verify_quotes.py,
# validate.py) need a shell, curl and `claude -p`; a sub-agent has none of
# them. This MCP server is the shell's replacement: each tool runs one script
# with checked arguments and returns its output. It adds no logic of its own
# beyond argument checks and the build-stage report.
#
# Refuses: a slug that is not kebab-case, ids that are not catalogue ids,
# paths that leave the persona's folder, the cache or the temp directory.
# `fetch` reaches the network (the URLs of the persona's own source list);
# `validation_start` spends Claude quota. Both say so in their docstrings.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import functools
import json
import os
import re
import subprocess
import sys
import textwrap
import time
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parents[2]
sys.path.insert(0, str(HERE))
from common import CACHE_ROOT  # noqa: E402

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
WORK_ROOT = Path("/tmp/gandalf-persona")
SOURCE_FIELDS = {"id", "url", "title", "source_type", "source_date", "tags", "from", "start", "end",
                 "collection", "layout", "ocr"}
LIMIT = 12000  # characters of script output returned

server = MCPServer(
    name="mirdain",
    log_level="WARNING",
    instructions=(
        "Tools for the F.I.N.R.O.D. sub-agent, which builds White Council persona cards: "
        "wrappers of the scripts in .claude/scripts/personas/. Hand a persona build to "
        "Finrod rather than calling these tools yourself."
    ),
)


class Refused(Exception):
    pass


def _brain() -> Path:
    raw = ""
    try:
        for line in (PROJECT_DIR / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("BRAIN_PATH="):
                raw = line.partition("=")[2].strip().strip("\"'")
    except OSError:
        pass
    path = Path(os.path.expanduser(raw or "../brain"))
    return (path if path.is_absolute() else PROJECT_DIR / path).resolve()


def _slug(slug: str) -> str:
    if not SLUG_RE.match(slug or "") or len(slug) > 60:
        raise Refused("slug must be kebab-case (a-z, 0-9, hyphens), at most 60 characters")
    return slug


def _persona_dir(slug: str) -> Path:
    folder = _brain() / "knowledge" / "personas" / _slug(slug)
    if not folder.parent.is_dir():
        raise Refused(f"{folder.parent} does not exist — BRAIN_PATH wrong or brain/ not initialised")
    return folder


def _ids(ids: list[str]) -> list[str]:
    if not ids:
        raise Refused("no source ids given")
    for i in ids:
        if not ID_RE.match(i or ""):
            raise Refused(f"'{i}' is not a catalogue id")
    return ids


def _run(args: list[str], timeout: int = 900) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(HERE / args[0]), *args[1:]], capture_output=True,
                          text=True, timeout=timeout, cwd=PROJECT_DIR)
    out = (proc.stdout + proc.stderr).strip()
    if len(out) > LIMIT:
        out = out[:LIMIT] + f"\n… [{len(out) - LIMIT} more characters cut]"
    return proc.returncode, out


def _guard(fn):
    # functools.wraps keeps the signature and annotations: the MCP SDK builds
    # the tool's input schema from them (without it the schema is `a`, `kw`).
    @functools.wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except (Refused, OSError, subprocess.SubprocessError, ValueError) as exc:
            return f"MIRDAIN: refused — {exc}"
    return wrapper


RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
RW = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
NET = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)


@server.tool(annotations=RO)
@_guard
def status(slug: str) -> str:
    """Where a persona's build stands, read from disk: scope, catalogue, digests done / total,
    card version, validation config and runs. Use it first on every turn of a build."""
    folder = _persona_dir(slug)
    if not folder.is_dir():
        return f"MIRDAIN: {slug} — no folder yet (stage: none)"
    lines = [f"MIRDAIN: {slug}"]
    sources_md = folder / "sources.md"
    if sources_md.is_file():
        text = sources_md.read_text(encoding="utf-8")
        lines.append(f"sources.md: yes; scope section: {'yes' if re.search(r'^## Zakres', text, re.M) else 'no'}")
        todo = len(re.findall(r"\|\s*todo\s*\|", text))
        done = len(re.findall(r"\|\s*esencja\s*\|", text))
        lines.append(f"catalogue rows: {done} esencja, {todo} todo")
    else:
        lines.append("sources.md: no")
    lines.append(f"sources.json: {'yes' if (folder / 'sources.json').is_file() else 'no'}")
    digests = folder / "sources"
    lines.append(f"digest files: {len(list(digests.glob('*.md'))) if digests.is_dir() else 0}")
    card = folder / "persona.md"
    if card.is_file():
        m = re.search(r"^card_version:\s*(\S+)", card.read_text(encoding="utf-8"), re.M)
        lines.append(f"persona.md: yes, card_version {m.group(1) if m else '?'}")
    else:
        lines.append("persona.md: no")
    lines.append(f"validation.json: {'yes' if (folder / 'validation.json').is_file() else 'no'}; "
                 f"validation.md: {'yes' if (folder / 'validation.md').is_file() else 'no'}")
    runs = CACHE_ROOT / slug / "validation"
    if runs.is_dir():
        lines.append("validation runs: " + ", ".join(sorted(p.name for p in runs.iterdir() if p.is_dir())))
    return "\n".join(lines)


@server.tool(annotations=RW)
@_guard
def catalog_put(slug: str, sources: list[dict]) -> str:
    """Write the persona's source list to brain/knowledge/personas/<slug>/sources.json.
    Each entry needs `id` (<date>-<slug-of-title>) and a public http(s) `url`; optional: title,
    source_type, source_date, tags, and the excerpt fields from, start, end (see fetch.py).
    Replaces the file; the old content is not kept (git has it)."""
    folder = _persona_dir(slug)
    if not sources:
        raise Refused("empty source list")
    seen = set()
    for s in sources:
        extra = set(s) - SOURCE_FIELDS
        if extra:
            raise Refused(f"unknown fields {sorted(extra)} in {s.get('id')!r}")
        if not ID_RE.match(str(s.get("id", ""))) or s["id"] in seen:
            raise Refused(f"missing, malformed or duplicate id: {s.get('id')!r}")
        seen.add(s["id"])
        if "from" in s:
            if s["from"] not in seen and not any(t.get("id") == s["from"] for t in sources):
                raise Refused(f"{s['id']}: excerpt of unknown source {s['from']!r}")
            continue
        if not re.match(r"^https?://", str(s.get("url", ""))):
            raise Refused(f"{s['id']}: url must be http(s)")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"MIRDAIN: sources.json written — {len(sources)} entries"


@server.tool(annotations=NET)
@_guard
def fetch(slug: str, wayback: bool = True, only: list[str] | None = None) -> str:
    """Download the sources of sources.json (network: only the URLs in that list), extract text,
    record sha256 and word counts, and print the sources.md rows with totals. Cached originals are
    reused. `only` limits it to the given ids. Can take minutes."""
    _persona_dir(slug)
    base = ["fetch.py", slug]
    if wayback:
        base.append("--wayback")
    if only:
        base += ["--only", ",".join(_ids(only))]
    code, out = _run(base, timeout=1800)
    if code:
        return f"MIRDAIN: fetch.py failed ({code})\n{out}"
    _, table = _run(["fetch.py", slug, "--table"])
    return f"{out}\n\n--- sources.md rows ---\n{table}"


@server.tool(annotations=RW)
@_guard
def prepare(slug: str, ids: list[str]) -> str:
    """Prepare sources for Narvi: the text, one paragraph per line, folded at 1500 characters, written
    to /tmp/gandalf-persona/<slug>/text/<id>.txt. Returns the paths and word counts."""
    _persona_dir(slug)
    out_dir = WORK_ROOT / slug / "text"
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in _ids(ids):
        proc = subprocess.run([sys.executable, str(HERE / "reflow.py"), slug, i], capture_output=True,
                              text=True, cwd=PROJECT_DIR)
        if proc.returncode:
            lines.append(f"{i}: FAILED — {proc.stderr.strip()[-300:]}")
            continue
        folded = "\n".join(
            textwrap.fill(p, width=1500, break_long_words=False, break_on_hyphens=False) if p.strip() else p
            for p in proc.stdout.splitlines())
        target = out_dir / f"{i}.txt"
        target.write_text(folded + "\n", encoding="utf-8")
        lines.append(f"{i}: {target} — {len(proc.stdout.split())} words")
    return "MIRDAIN: prepared\n" + "\n".join(lines)


@server.tool(annotations=RW)
@_guard
def assemble(slug: str, drafts_dir: str, ids: list[str], write: bool = False) -> str:
    """Check the quotes of digest drafts against their sources (`write` false), or check and write the
    digests into brain/knowledge/personas/<slug>/sources/ and flip todo → esencja in sources.md
    (`write` true). `drafts_dir` lies under /tmp. A missing quote: fix the draft, never the checker."""
    _persona_dir(slug)
    folder = Path(drafts_dir).resolve()
    if Path("/tmp").resolve() not in folder.parents and folder != Path("/tmp").resolve():
        raise Refused("drafts_dir must be under /tmp")
    args = ["assemble.py", slug, str(folder), ",".join(_ids(ids))]
    if write:
        args.append("--write")
    code, out = _run(args)
    return f"MIRDAIN: assemble exit {code}\n{out}"


@server.tool(annotations=RO)
@_guard
def verify_quotes(slug: str, ids: list[str] | None = None) -> str:
    """Check every quote of the finished digests against the source text. No ids = all digests."""
    _persona_dir(slug)
    code, out = _run(["verify_quotes.py", slug, *(_ids(ids) if ids else [])])
    return f"MIRDAIN: verify_quotes exit {code}\n{out}"


@server.tool(annotations=RW)
@_guard
def validation_put(slug: str, config: dict) -> str:
    """Write validation.json (dilemmas, judge rubric, tic patterns — see references/validation.md)
    to the persona's folder. It must be an object with `name` and a non-empty `dilemmas` list."""
    folder = _persona_dir(slug)
    if not folder.is_dir():
        raise Refused(f"{slug} has no folder")
    if not str(config.get("name", "")).strip() or not isinstance(config.get("dilemmas"), list) or not config["dilemmas"]:
        raise Refused("config needs `name` and a non-empty `dilemmas` list")
    (folder / "validation.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"MIRDAIN: validation.json written — {len(config['dilemmas'])} dilemmas"


@server.tool(annotations=RW)
@_guard
def validation_start(slug: str, run: str = "", reuse_bare: str = "") -> str:
    """Start validate.py as a detached process (it spends Claude quota: ~72 answers and 12 judge calls,
    an hour or more). It saves after each call, so starting the same `run` again resumes it. Start it
    only when the owner has said so. Poll with validation_status."""
    _persona_dir(slug)
    args = [sys.executable, str(HERE / "validate.py"), slug]
    for flag, value in (("--run", run), ("--reuse-bare", reuse_bare)):
        if value:
            if not ID_RE.match(value):
                raise Refused(f"'{value}' is not a run name")
            args += [flag, value]
    log_dir = WORK_ROOT / slug
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"validate-{run or 'default'}.log"
    with open(log, "a") as fh:
        fh.write(f"\n--- started {datetime.now().isoformat(timespec='seconds')} ---\n")
        proc = subprocess.Popen(args, stdout=fh, stderr=subprocess.STDOUT, cwd=PROJECT_DIR, start_new_session=True)
    time.sleep(2)
    if proc.poll() not in (None, 0):
        return f"MIRDAIN: validate.py exited at once ({proc.returncode}) — see {log}"
    return f"MIRDAIN: validation started (pid {proc.pid}), log {log}"


@server.tool(annotations=RO)
@_guard
def validation_status(slug: str, run: str = "") -> str:
    """The tail of the validation log and, for a finished run, its summary (validate.py --report)."""
    _persona_dir(slug)
    logs = sorted((WORK_ROOT / slug).glob(f"validate-{run or '*'}.log"), key=lambda p: p.stat().st_mtime)
    tail = "no log yet"
    if logs:
        tail = f"{logs[-1].name} (modified {datetime.fromtimestamp(logs[-1].stat().st_mtime).isoformat(timespec='seconds')}):\n" + \
            "\n".join(logs[-1].read_text(errors="replace").splitlines()[-15:])
    runs = CACHE_ROOT / slug / "validation"
    names = [run] if run else (sorted(p.name for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else [])
    report = ""
    if names:
        code, out = _run(["validate.py", slug, "--report", *[_ids([n])[0] for n in names]])
        report = f"\n\n--- report (exit {code}) ---\n{out}"
    return f"MIRDAIN: {tail}{report}"


if __name__ == "__main__":
    server.run("stdio")
