#!/usr/bin/env python3
# A read-only look at the Raspberry Pi's user services, as MCP tools, for
# A.U.L.E. only (only his `tools:` names them). Logic and the allowlists are in
# readops.py:
#
#   systemd_cat      the unit file and drop-ins of one allowed unit
#   systemd_status   state of the allowed units (a name or a `gandalf*` pattern)
#   systemd_timers   the user timers and when they next fire
#   journal_tail     the last N journal lines of one allowed unit
#   tmux_ls          the tmux sessions (names and state only, no pane content)
#
# Nothing here starts, stops, restarts or edits anything, and no tool takes a
# path. Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

sys.path.insert(0, str(Path(__file__).resolve().parent))

import readops  # noqa: E402

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

server = MCPServer(
    name="rpi",
    log_level="WARNING",
    instructions=(
        "Read-only view of the Raspberry Pi's user systemd units (gandalf*, samwise-mcp), their "
        "journal and the tmux sessions. For A.U.L.E. Nothing here changes anything; a refusal "
        "(REFUSED: ...) is final."
    ),
)


@server.tool(annotations=READ)
def systemd_cat(unit: str) -> str:
    """The unit file and drop-ins of one user unit, e.g. `gandalf-restart.timer`.
    Only gandalf* and samwise-mcp units; lines that look like secrets are blanked."""
    return readops.systemd_cat(unit)


@server.tool(annotations=READ)
def systemd_status(pattern: str = "gandalf*") -> str:
    """State of user units: a pattern such as `gandalf*` lists them, a full name
    (`gandalf-restart.service`) shows its status without the journal."""
    return readops.systemd_status(pattern)


@server.tool(annotations=READ)
def systemd_timers() -> str:
    """The user timers: next and last run, and the unit each one starts."""
    return readops.systemd_timers()


@server.tool(annotations=READ)
def journal_tail(unit: str, n: int = 50) -> str:
    """The last `n` journal lines (1 to 200, default 50) of one allowed user unit."""
    return readops.journal_tail(unit, n)


@server.tool(annotations=READ)
def tmux_ls() -> str:
    """The tmux sessions of the default socket: name, windows, created, attached.
    No pane content."""
    return readops.tmux_ls()


if __name__ == "__main__":
    server.run("stdio")
