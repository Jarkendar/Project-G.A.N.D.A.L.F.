# The git side of the router's `sync` MCP server — kept apart from the server
# so it can be tested without the MCP SDK (test_sync_tools.py).
#
# Three operations over two fixed repositories, this one and brain/:
#
#   status          branch, tree clean or dirty, last commit, ahead / behind
#   log             the last N commits (subjects only, N from 1 to 30)
#   checkout_main   back to `main` after a merge — only on a clean tree, only
#                   with nothing unpushed, only fast-forward after a fetch
#
# No commit, push, branch, merge, reset, stash: Aulë and Ori own those. The
# caller never passes a path or a git argument — only a repo name from a fixed
# list and a number. Every git call goes through `git()`, which accepts a fixed
# set of sub-commands and runs without a shell.

import fcntl
import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_DIR / ".claude" / "hooks" / "brain-instruction-sync"))

from sync import LOCK_FILE, read_brain_path  # noqa: E402  (the hook's lock and env reader)

# Sub-command -> the one argument that must be present (and, where it could do
# harm with others, the only one allowed): `branch` only to read the name,
# `switch` only to `main`, `pull` only fast-forward, `fetch` only from origin.
ALLOWED = {"status": None, "log": None, "rev-list": None, "rev-parse": None,
           "branch": ("--show-current",), "switch": ("main", "--quiet"),
           "pull": ("--ff-only", "--quiet"), "fetch": ("origin", "--quiet")}
TIMEOUT = 30
MAX_LOG = 30
MAX_LISTED = 10
REPOS = ("gandalf", "brain")
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")


def git(repo, *args):
    if not args or args[0] not in ALLOWED:
        raise ValueError(f"git {args[:1]} is not allowed here")
    exact = ALLOWED[args[0]]
    if exact is not None and args[1:] != exact:
        raise ValueError(f"git {' '.join(args)} is not allowed here")
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                          timeout=TIMEOUT, env=ENV, stdin=subprocess.DEVNULL)


def paths(project_dir=None):
    """Name -> path of the two repos; brain/ is None when it cannot be found."""
    project_dir = str(project_dir or PROJECT_DIR)
    brain = read_brain_path(project_dir)
    return {"gandalf": project_dir, "brain": brain if brain and os.path.isdir(brain) else None}


def head_of(repo):
    out = git(repo, "rev-parse", "--short", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else None


def branch_of(repo):
    return git(repo, "branch", "--show-current").stdout.strip() or "detached HEAD"


def dirty_files(repo):
    out = git(repo, "status", "--porcelain")
    return [ln[3:] for ln in out.stdout.splitlines() if ln.strip()]


def listed(files):
    shown = ", ".join(files[:MAX_LISTED])
    return shown + (f", … (+{len(files) - MAX_LISTED})" if len(files) > MAX_LISTED else "")


def status_one(repo, name):
    try:
        head = head_of(repo)
        if head is None:
            return f"{name}: not a git repo"
        files = dirty_files(repo)
        tree = f"dirty: {len(files)} files ({listed(files)})" if files else "clean"
        last = git(repo, "log", "-1", "--format=%h %s").stdout.strip()
        if git(repo, "rev-parse", "--abbrev-ref", "@{u}").returncode != 0:
            upstream = "no upstream"
        else:
            counts = git(repo, "rev-list", "--left-right", "--count", "@{u}...HEAD").stdout.split()
            upstream = f"behind {counts[0]}, ahead {counts[1]} (as of the last fetch)" if len(counts) == 2 else "upstream unknown"
        return f"{name}: {branch_of(repo)} | {tree} | {last} | {upstream}"
    except (OSError, subprocess.SubprocessError):
        return f"{name}: status failed"


def status(project_dir=None):
    found = paths(project_dir)
    return "\n".join(status_one(found[n], n) if found[n] else f"{n}: not found" for n in REPOS)


def log(repo, n=10, project_dir=None):
    if repo not in REPOS:
        return f"SYNC: unknown repo '{repo}' — one of {', '.join(REPOS)}"
    try:
        count = max(1, min(MAX_LOG, int(n)))
    except (TypeError, ValueError):
        return "SYNC: n must be a number from 1 to 30"
    path = paths(project_dir)[repo]
    if not path:
        return f"{repo}: not found"
    try:
        out = git(path, "log", "--oneline", f"-{count}")
    except (OSError, subprocess.SubprocessError):
        return f"{repo}: log failed"
    return out.stdout.strip() if out.returncode == 0 else f"{repo}: no history ({out.stderr.strip()})"


def checkout_main_one(repo, name):
    try:
        before = head_of(repo)
        if before is None:
            return f"{name}: not a git repo"
        branch = branch_of(repo)
        files = dirty_files(repo)
        if files:
            return f"{name}: REFUSED — the tree is dirty, {len(files)} files ({listed(files)}); nothing changed"
        if branch != "main":
            if branch == "detached HEAD":
                return f"{name}: REFUSED — detached HEAD at {before}; nothing changed"
            unpushed = git(repo, "rev-list", "--count", "HEAD", "--not", "--remotes").stdout.strip()
            if unpushed != "0":
                return (f"{name}: REFUSED — {branch} has {unpushed or '?'} commit(s) on no remote "
                        "(unpushed work); nothing changed")
        if git(repo, "fetch", "origin", "--quiet").returncode != 0:
            return f"{name}: offline — fetch failed, nothing changed (on {branch} at {before})"
        if branch != "main" and git(repo, "switch", "main", "--quiet").returncode != 0:
            return f"{name}: REFUSED — could not switch to main; still on {branch} at {before}"
        if git(repo, "pull", "--ff-only", "--quiet").returncode != 0:
            return f"{name}: on main, DIVERGED or no upstream — not pulled; the owner merges by hand (at {head_of(repo)})"
        after = head_of(repo)
        moved = f"{before} -> {after}" if before != after else f"up to date ({after})"
        return f"{name}: {branch} -> main, {moved}" if branch != "main" else f"{name}: main, {moved}"
    except (OSError, subprocess.SubprocessError):
        return f"{name}: checkout_main failed, skipped"


def checkout_main(repo="both", project_dir=None):
    if repo not in REPOS + ("both",):
        return f"SYNC: unknown repo '{repo}' — one of {', '.join(REPOS)}, both"
    found = paths(project_dir)
    chosen = REPOS if repo == "both" else (repo,)
    try:
        lock = open(LOCK_FILE, "w")
    except OSError:
        return "SYNC: could not open the lock file — nothing changed"
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return "sync: skipped, another session holds the lock"
    try:
        return "\n".join(checkout_main_one(found[n], n) if found[n] else f"{n}: not found" for n in chosen)
    finally:
        lock.close()
