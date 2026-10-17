#!/usr/bin/env python3
# Repo sync for the router, as one MCP tool, so Gandalf needs no shell:
#
#   pull   `git pull --ff-only` on this repo and on brain/ — the same pass the
#          SessionStart hook makes (.claude/hooks/brain-instruction-sync/
#          sync.py), on demand, e.g. right after the owner merged a PR.
#
# No arguments: the two repositories are fixed (this one, and BRAIN_PATH from
# .claude/gandalf.env). Fast-forward only — a pull that would merge is reported
# as DIVERGED and left to the owner. The lock is the hook's, so a pull here and
# one at a session start never race.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / ".claude" / "hooks" / "brain-instruction-sync"))

from sync import pull_repos, read_brain_path  # noqa: E402

server = MCPServer(
    name="sync",
    log_level="WARNING",
    instructions=(
        "Fast-forwards this repository and brain/ from their remotes (git pull --ff-only). "
        "Call it when the owner asks to update the repos, e.g. after merging a pull request."
    ),
)


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
def pull() -> str:
    """Fast-forward both repositories — G.A.N.D.A.L.F. and brain/ — from their
    remotes. One line per repo: `up to date (<sha>)`, `<old> -> <new>`, or
    `DIVERGED or offline` (nothing changed; the owner merges by hand). If this
    repo moved, agent definitions and hooks take effect in a new session only."""
    brain = read_brain_path(str(PROJECT_DIR))
    if not brain or not Path(brain).is_dir():
        return "SYNC: BRAIN_PATH is not set or does not exist — nothing pulled"
    report = pull_repos(str(PROJECT_DIR), brain)
    if not report:
        return "SYNC: could not open the lock file — nothing pulled"
    return "\n".join(report)


if __name__ == "__main__":
    server.run("stdio")
