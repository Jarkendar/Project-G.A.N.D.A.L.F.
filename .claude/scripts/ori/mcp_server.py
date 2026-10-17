#!/usr/bin/env python3
# O.R.I. — Orderly Record Inscriber.
#
# The one place that may commit and push brain/. Two MCP tools, so the Ori
# sub-agent needs no shell and no other agent needs git:
#   - status: what is changed in brain/ (file names only);
#   - commit: `git add` exactly the paths given, one commit, push.
#
# What it will not do, by construction: touch any repository but BRAIN_PATH
# (from .claude/gandalf.env); commit on a branch other than main; stage
# anything it was not handed (no `-A`, no repository root); delete, amend,
# rebase, force or skip brain/'s pre-commit hook. The commit trailer is added
# here, not left to the caller. `commit` takes an optional `date` (YYYY-MM-DD)
# that sets GIT_AUTHOR_DATE and GIT_COMMITTER_DATE for that one commit.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import os
import re
import subprocess
from datetime import datetime, time, timedelta
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]

BRANCH = "main"
TRAILER = "Co-Authored-By: Claude <noreply@anthropic.com>"
SUBJECT_RE = re.compile(r"^(feat|fix|docs|chore|refactor)(\([a-z0-9][a-z0-9-]*\))?: \S.{2,}$")
MAX_SUBJECT = 100
MAX_PATHS = 2000
GIT_TIMEOUT_S = 60
# An optional date for a commit (a `daily` filed the next day): YYYY-MM-DD only,
# never in the future, at most this many days back, at noon local time.
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_BACKDATE_DAYS = 7
COMMIT_HOUR = 12

server = MCPServer(
    name="ori",
    log_level="WARNING",
    instructions=(
        "Commits and pushes the owner's brain/ repository — only the paths it is handed, only "
        "on main. Committing belongs to the O.R.I. sub-agent: hand it the paths that were "
        "written and what they are, rather than calling these tools yourself."
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
    path = path if path.is_absolute() else PROJECT_DIR / path
    path = path.resolve()
    if not (path / ".git").exists():
        raise Refused(f"BRAIN_PATH ({path}) is not a git repository")
    return path


def _now() -> datetime:
    return datetime.now().astimezone()


def _commit_date(date: object) -> str | None:
    """`YYYY-MM-DD` -> an ISO timestamp with the local offset, or None for no date.
    Noon of that day; for today, the current time (a commit never runs ahead of
    the clock). Refuses a bad format, a day that does not exist, the future and
    anything older than MAX_BACKDATE_DAYS."""
    if date is None:
        return None
    if not isinstance(date, str) or not DATE_RE.match(date):
        raise Refused(f"date must be YYYY-MM-DD, got {date!r}")
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise Refused(f"{date} is not a real day")
    now = _now()
    if day > now.date():
        raise Refused(f"date {date} is in the future")
    if day < now.date() - timedelta(days=MAX_BACKDATE_DAYS):
        raise Refused(f"date {date} is more than {MAX_BACKDATE_DAYS} days back")
    if day == now.date():
        return now.replace(microsecond=0).isoformat()
    return datetime.combine(day, time(COMMIT_HOUR)).astimezone().isoformat(timespec="seconds")


def _git(brain: Path, *args: str, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-C", str(brain), *args],
        capture_output=True, text=True, timeout=GIT_TIMEOUT_S,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})},
    )
    if check and proc.returncode != 0:
        raise Refused(f"git {args[0]} failed: {(proc.stderr or proc.stdout).strip()[:800]}")
    return proc


def _on_main(brain: Path) -> None:
    branch = _git(brain, "branch", "--show-current").stdout.strip()
    if branch != BRANCH:
        raise Refused(f"brain/ is on '{branch or 'a detached HEAD'}', not {BRANCH} — nothing done")


def _clean_paths(brain: Path, paths: list[str]) -> list[str]:
    if not paths:
        raise Refused("no paths given")
    if len(paths) > MAX_PATHS:
        raise Refused(f"more than {MAX_PATHS} paths in one commit")
    clean = []
    for raw in paths:
        if not isinstance(raw, str) or not raw.strip() or raw.startswith("-"):
            raise Refused(f"not a path: {raw!r}")
        full = Path(raw) if os.path.isabs(raw) else brain / raw
        if not full.exists():
            raise Refused(f"{raw} does not exist — this tool adds and changes files, it never deletes")
        if full.is_symlink():
            raise Refused(f"{raw} is a symlink")
        resolved = full.resolve()
        if resolved == brain or brain not in resolved.parents:
            raise Refused(f"{raw} is not a path inside brain/")
        rel = resolved.relative_to(brain)
        if rel.parts[0] == ".git":
            raise Refused(f"{raw} is inside .git")
        clean.append(rel.as_posix())
    return sorted(set(clean))


def _status_text(brain: Path) -> str:
    out = _git(brain, "status", "--short", "--branch", "--untracked-files=all").stdout.rstrip()
    return out or "(clean)"


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def status() -> str:
    """What is changed in brain/: the branch line, then one line per changed or
    untracked file (`git status --short`). File names only, no content."""
    try:
        brain = _brain()
        return _status_text(brain)
    except (Refused, subprocess.TimeoutExpired) as exc:
        return f"ORI: {exc}"


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
def commit(paths: list[str], message: str, date: str | None = None) -> str:
    """Stage exactly `paths` (files or folders, relative to brain/), make one commit
    on main and push it. `message` is a Conventional Commits subject in English —
    `feat(councils): …`, `docs(core): …` — optionally followed by a blank line and
    a body; the Co-Authored-By trailer is added for you. `date` (optional,
    `YYYY-MM-DD`) dates the commit — author and committer — at noon of that day,
    for a record filed the next day; not in the future, at most 7 days back. Left
    out, the commit has the time it is made. Anything already staged by someone
    else, a branch other than main, a missing path or a path outside brain/ is
    refused and nothing is changed. If the push fails the commit stays local and
    the reply says so."""
    try:
        brain = _brain()
        _on_main(brain)
        stamp = _commit_date(date)
        subject, _, body = message.strip().partition("\n")
        subject = subject.strip()
        if not SUBJECT_RE.match(subject) or len(subject) > MAX_SUBJECT:
            raise Refused(
                "the message must start with a Conventional Commits subject of at most "
                f"{MAX_SUBJECT} characters, e.g. 'feat(councils): flat in Poznań vs renting'"
            )
        if "Co-Authored-By" in message or "Claude-Session" in message:
            raise Refused("leave trailers out of the message — the server adds the one that belongs")
        rel = _clean_paths(brain, paths)
        staged = _git(brain, "diff", "--cached", "--name-only").stdout.split("\n")
        staged = [s for s in staged if s]
        if staged:
            raise Refused(
                "brain/ already has staged changes that are not from this call "
                f"({', '.join(staged[:5])}{'…' if len(staged) > 5 else ''}) — nothing done"
            )
        _git(brain, "add", "--", *rel)
        to_commit = [s for s in _git(brain, "diff", "--cached", "--name-only").stdout.split("\n") if s]
        if not to_commit:
            return "ORI: nothing to commit — the given paths have no changes"
        deleted = [s for s in _git(brain, "diff", "--cached", "--name-only", "--diff-filter=D").stdout.split("\n") if s]
        if deleted:
            _git(brain, "reset", "-q", "--", *rel)
            raise Refused(f"the paths include deletions ({', '.join(deleted[:5])}) — brain/ is append-only; nothing committed")
        full_message = subject + ("\n\n" + body.strip() if body.strip() else "") + "\n\n" + TRAILER
        when = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp} if stamp else None
        done = _git(brain, "commit", "-q", "-m", full_message, check=False, env=when)
        if done.returncode != 0:
            _git(brain, "reset", "-q", "--", *rel)
            raise Refused(f"the commit was rejected (pre-commit hook?): {(done.stderr or done.stdout).strip()[:1200]}")
        sha = _git(brain, "rev-parse", "--short", "HEAD").stdout.strip()
        listing = "\n".join(f"  {f}" for f in to_commit[:40]) + (f"\n  … and {len(to_commit) - 40} more" if len(to_commit) > 40 else "")
        pushed = _git(brain, "push", "-q", "origin", BRANCH, check=False)
        if pushed.returncode != 0:
            return (
                f"ORI: committed {sha}{f' (dated {stamp})' if stamp else ''} ({len(to_commit)} file(s)) but the PUSH FAILED — the commit is local only.\n"
                f"{(pushed.stderr or pushed.stdout).strip()[:800]}\n{listing}"
            )
        dated = f" (dated {stamp})" if stamp else ""
        return f"ORI: committed and pushed {sha} to {BRANCH}{dated} — {subject}\n{len(to_commit)} file(s):\n{listing}"
    except subprocess.TimeoutExpired:
        return f"ORI: git did not answer within {GIT_TIMEOUT_S} s — check brain/ by hand"
    except Refused as exc:
        return f"ORI: refused — {exc}"


if __name__ == "__main__":
    server.run("stdio")
