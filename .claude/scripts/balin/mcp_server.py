#!/usr/bin/env python3
# B.A.L.I.N. — the archive of an English-practice session's raw transcripts.
#
#   archive_transcripts  the transcripts of an `english-review` → one new file
#                        each in brain/conversations/, the way /ingest-conversation
#                        stores a dropped transcript (summary + verbatim text,
#                        sha256 for dedup). The logic is archive.py.
#
# Belongs to the Balin sub-agent, which has no shell to hash a transcript or to
# copy it unchanged. Writes new files into conversations/ only.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

import archive

PROJECT_DIR = Path(__file__).resolve().parents[3]

server = MCPServer(
    name="balin",
    log_level="WARNING",
    instructions=(
        "Archives the raw transcripts of an English-practice review into brain/conversations/. "
        "It belongs to the B.A.L.I.N. sub-agent — hand an English review to him rather than "
        "calling this tool yourself."
    ),
)


def _brain() -> Path:
    raw = ""
    try:
        for line in (PROJECT_DIR / ".claude" / "gandalf.env").read_text().splitlines():
            if line.strip().startswith("BRAIN_PATH="):
                raw = line.partition("=")[2].strip().strip("\"'")
    except OSError:
        pass
    path = Path(os.path.expanduser(raw or "../brain"))
    return (path if path.is_absolute() else PROJECT_DIR / path).resolve()


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def archive_transcripts(items: list[dict], now: str, dry_run: bool = False) -> str:
    """Archive raw transcripts as new files in brain/conversations/. `items`: a
    list (at most 10) of {title (one line, ≤60 chars), summary (2–4 sentences),
    tags (1–4 lowercase kebab-case topic tags), transcript (the raw text, exactly
    as given)}. `now`: an ISO 8601 timestamp (from the `now` tool); item N gets
    now + N-1 seconds. The tool adds the tags `english-review` and the assistant,
    detects the assistant from the `Claude: ` / `Gemini: ` lines, hashes the
    transcript and skips one already archived (same content_hash, also from
    /ingest-conversation). Never overwrites, never creates the folder, writes
    nothing else; whole or nothing. With `dry_run` nothing is written — it
    returns the file names and the duplicates, for the plan."""
    try:
        plan = archive.archive(_brain(), items, now, dry_run)
    except (archive.Refused, OSError) as exc:
        return f"BALIN: refused — {exc}"
    head = "BALIN: would archive" if dry_run else "BALIN: archived"
    lines = []
    for e in plan:
        if e["duplicate_of"]:
            lines.append(f"  {e['index']}. DUPLICATE — skipped, same content_hash as {e['duplicate_of']} ({e['title']})")
        else:
            lines.append(
                f"  {e['index']}. conversations/{e['name']} — {e['title']} | assistant {e['assistant']} | "
                f"{e['lines']} lines, {e['chars']} chars | {e['content_hash'][:19]}…"
            )
    return f"{head} {sum(1 for e in plan if not e['duplicate_of'])} of {len(plan)}:\n" + "\n".join(lines)


if __name__ == "__main__":
    server.run("stdio")
