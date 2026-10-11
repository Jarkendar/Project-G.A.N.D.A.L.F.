#!/usr/bin/env python3
# E.L.R.O.N.D. — Examiner Laying out Rounds' Outcomes, Noting Dissent.
#
# One MCP tool for the Elrond sub-agent: `record` puts a White Council's
# record together from the files of its working folder — the synthesis Elrond
# wrote and every voice's answer exactly as the voice wrote it — and writes
# it to brain/knowledge/councils/. The answers are copied, not retyped: a
# record of five voices and two rounds is ~60k characters, and no model
# should be asked to write that out again from memory.
#
# The working folder (in the session scratchpad):
#   question.md              the framed question with the owner's context
#   blind-<voice>.md         one per voice, the blind round
#   critique-<voice>.md      the critique round
#   critique2-<voice>.md     a second critique round, if there was one
#   synthesis.md             Elrond's synthesis
#
# It writes one new file and nothing else: it refuses to overwrite a record
# (they are never edited — knowledge/councils/CLAUDE.md), to read a folder
# outside the temp directory, and to write anywhere but knowledge/councils/.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ROUNDS = (("blind", "Runda na ślepo"), ("critique", "Krytyka"), ("critique2", "Krytyka 2"))

server = MCPServer(
    name="elrond",
    log_level="WARNING",
    instructions=(
        "Assembles the record of a White Council from its working files and writes it to "
        "brain/knowledge/councils/. It belongs to the E.L.R.O.N.D. sub-agent, which writes "
        "the Council's synthesis — hand the Council's folder to it rather than calling this "
        "tool yourself."
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


def _council_dir(raw: str) -> Path:
    path = Path(raw).resolve()
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    if not any(root in path.parents for root in roots):
        raise Refused(f"{path} is not under the temp directory — the Council's folder lives in the scratchpad")
    if not path.is_dir():
        raise Refused(f"{path} is not a folder")
    return path


def _read(path: Path) -> str:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise Refused(f"{path.name} is empty")
    return text


def _yaml_str(value: str) -> str:
    return json.dumps(" ".join(value.split()), ensure_ascii=False)


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def record(
    council_dir: str,
    slug: str,
    title: str,
    question: str,
    voices: list[dict],
    tags: list[str],
    consensus: str,
) -> str:
    """Write the record of one White Council to brain/knowledge/councils/<today>_<slug>.md.

    `council_dir` — the Council's working folder in the scratchpad. `slug` —
    kebab-case, at most 40 characters, from the question. `title` — the question in
    a few words (the tool adds "Rada — "). `question` — the framed question in one
    or two sentences. `voices` — in speaking order, each {"slug": the card's slug as
    used in the file names, "name": the name to show}. `tags` — topic tags
    (`council` is added). `consensus` — yes | no | partial.

    The synthesis and every answer are copied from the folder as they are. The
    number of critique rounds is counted from the files. Call it only after the
    owner said yes to saving."""
    try:
        folder = _council_dir(council_dir)
        if not SLUG_RE.match(slug) or len(slug) > 40:
            raise Refused("slug must be kebab-case (a-z, 0-9, hyphens), at most 40 characters")
        if consensus not in ("yes", "no", "partial"):
            raise Refused("consensus must be yes, no or partial")
        if not title.strip() or not question.strip():
            raise Refused("title and question must not be empty")
        if not voices:
            raise Refused("no voices given")
        names = {}
        for voice in voices:
            v_slug, v_name = str(voice.get("slug", "")).strip(), str(voice.get("name", "")).strip()
            if not SLUG_RE.match(v_slug) or not v_name:
                raise Refused(f"each voice needs a kebab-case slug and a name — got {voice!r}")
            names[v_slug] = v_name
        clean_tags = []
        for tag in ["council", *tags]:
            tag = str(tag).strip().lower()
            if not SLUG_RE.match(tag):
                raise Refused(f"tag '{tag}' must be kebab-case")
            if tag not in clean_tags:
                clean_tags.append(tag)

        synthesis = _read(folder / "synthesis.md")
        framed = _read(folder / "question.md") if (folder / "question.md").is_file() else ""
        sections, critique_rounds, spoke = [], 0, set()
        for key, heading in ROUNDS:
            answers = [(s, folder / f"{key}-{s}.md") for s in names]
            answers = [(s, p) for s, p in answers if p.is_file()]
            if not answers:
                continue
            if key != "blind":
                critique_rounds += 1
            body = "\n\n".join(f"#### {names[s]}\n\n{_read(p)}" for s, p in answers)
            sections.append(f"### {heading}\n\n{body}")
            spoke.update(s for s, _ in answers)
        silent = [s for s in names if s not in spoke]
        if silent:
            raise Refused(f"no answer file in {folder} for: {', '.join(silent)}")
        unknown = sorted(
            p.name for p in folder.glob("*.md")
            if p.name not in ("synthesis.md", "question.md")
            and not any(p.name == f"{key}-{s}.md" for key, _ in ROUNDS for s in names)
        )
        if unknown:
            raise Refused(f"files in {folder} that belong to no listed voice: {', '.join(unknown)}")

        target_dir = _brain() / "knowledge" / "councils"
        if not target_dir.is_dir():
            raise Refused(f"{target_dir} does not exist — BRAIN_PATH wrong or brain/ not initialised")
        now = datetime.now().astimezone()
        target = target_dir / f"{now.strftime('%Y-%m-%d')}_{slug}.md"
        if target.exists():
            raise Refused(f"{target.name} already exists — a record is never overwritten; choose another slug")

        front = "\n".join([
            "---",
            f"date: {now.strftime('%Y-%m-%dT%H:%M:%S')}",
            "source: council",
            "privacy: private",
            "status: active",
            f"tags: [{', '.join(clean_tags)}]",
            f"title: {_yaml_str('Rada — ' + title.strip())}",
            f"question: {_yaml_str(question)}",
            f"voices: [{', '.join(names)}]",
            f"rounds: {critique_rounds}",
            f"consensus: {consensus}",
            "---",
        ])
        parts = [front, synthesis, "## Przebieg"]
        if framed:
            parts.append("### Pytanie (kontekst przekazany głosom)\n\n" + framed)
        parts += sections
        text = "\n\n".join(parts) + "\n"
        with open(target, "x", encoding="utf-8") as fh:
            fh.write(text)
        return (
            f"ELROND: record written — knowledge/councils/{target.name} "
            f"({len(text)} characters, {len(names)} voices, {critique_rounds} critique round(s))."
        )
    except (Refused, OSError, UnicodeDecodeError) as exc:
        return f"ELROND: refused — {exc}"


if __name__ == "__main__":
    server.run("stdio")
