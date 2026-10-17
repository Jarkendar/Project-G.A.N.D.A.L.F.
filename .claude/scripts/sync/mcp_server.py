#!/usr/bin/env python3
# Repo sync and git state for the router, as MCP tools, so Gandalf needs no shell:
#
#   pull   `git pull --ff-only` on this repo and on brain/ — the same pass the
#          SessionStart hook makes (.claude/hooks/brain-instruction-sync/
#          sync.py), on demand, e.g. right after the owner merged a PR.
#   status         both repos: branch, clean or dirty tree, last commit,
#                  ahead / behind (read-only)
#   log            the last N commits of one repo (read-only)
#   checkout_main  back to `main` after a merge: clean tree, nothing unpushed,
#                  fetch, then fast-forward only (logic in gitops.py)
#
# The two repositories are fixed (this one, and BRAIN_PATH from
# .claude/gandalf.env). Fast-forward only — a pull that would merge is reported
# as DIVERGED and left to the owner. The lock is the hook's, so a pull here and
# one at a session start never race. No commit, push, branch, merge or reset:
# those stay with Aulë and Ori.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / ".claude" / "hooks" / "brain-instruction-sync"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gitops  # noqa: E402
from sync import pull_repos, read_brain_path  # noqa: E402

server = MCPServer(
    name="sync",
    log_level="WARNING",
    instructions=(
        "Fast-forwards this repository and brain/ from their remotes (git pull --ff-only), "
        "and shows or restores their branch state. Call pull when the owner asks to update the "
        "repos, e.g. after merging a pull request; status for the branch and the tree; "
        "checkout_main to return to main after a merge. Nothing here commits, pushes or merges."
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


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
def status() -> str:
    """One line per repo — G.A.N.D.A.L.F. and brain/: the branch, whether the
    tree is clean (or which files are dirty), the last commit, and ahead /
    behind the upstream as of the last fetch. Changes nothing."""
    return gitops.status()


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False))
def log(repo: str, n: int = 10) -> str:
    """The last `n` commits (1 to 30, default 10) of `repo` — `gandalf` or
    `brain` — one line each, subjects only. Changes nothing."""
    return gitops.log(repo, n)


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
def checkout_main(repo: str = "both") -> str:
    """Return `repo` (`gandalf`, `brain` or `both`) to `main`: fetch, switch,
    `pull --ff-only`. Refused, with nothing changed, when the tree is dirty,
    HEAD is detached, or the current branch has commits on no remote. Never
    forces, resets, stashes, commits or pushes. A new `main` of this repo
    reaches agents and hooks in a new session only."""
    return gitops.checkout_main(repo)


if __name__ == "__main__":
    server.run("stdio")
