# Read-only look at the Raspberry Pi's user services, for Aulë (MCP server `rpi`).
#
# Five fixed operations — systemd_cat, systemd_status, systemd_timers,
# journal_tail, tmux_ls. No tool takes a path, so nothing outside the user
# systemd units and the journal is reachable (no ~/.ssh, no ~/.config, no env
# files). Every argument is validated before anything runs; commands are built
# as an argv list and run without a shell, with a minimal environment, a
# timeout and a cap on the output. Nothing here starts, stops, restarts or
# edits anything.
#
# Pure stdlib; the MCP layer is mcp_server.py. The runner is injectable so the
# tests need no systemd.

import os
import re
import subprocess

TIMEOUT_S = 10
MAX_OUTPUT = 20_000
MAX_JOURNAL_LINES = 200

# Unit families that may be looked at. Extending the list is a code change.
UNIT_FAMILIES = ("gandalf", "samwise-mcp")

UNIT_RE = re.compile(r"^[a-z0-9][a-z0-9_.@-]{0,63}\.(service|timer)$")
PATTERN_RE = re.compile(r"^[a-z0-9][a-z0-9_.@*-]{0,63}$")

SECRET_RE = re.compile(r"(key|token|secret|passw|pass=)", re.IGNORECASE)


class Refused(Exception):
    pass


def _family_ok(name):
    return any(name == f or name.startswith(f) for f in UNIT_FAMILIES)


def check_unit(unit):
    if not isinstance(unit, str) or not UNIT_RE.fullmatch(unit):
        raise Refused("unit must be a plain <name>.service or <name>.timer")
    if not _family_ok(unit):
        raise Refused(f"unit is not on the list ({', '.join(UNIT_FAMILIES)}*)")
    return unit


def check_pattern(pattern):
    if not isinstance(pattern, str) or not PATTERN_RE.fullmatch(pattern):
        raise Refused("pattern must be letters, digits, . _ @ - and *")
    if not _family_ok(pattern):
        raise Refused(f"pattern is not on the list ({', '.join(UNIT_FAMILIES)}*)")
    return pattern


def check_lines(n):
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= MAX_JOURNAL_LINES:
        raise Refused(f"n must be an integer from 1 to {MAX_JOURNAL_LINES}")
    return n


def _env():
    uid = os.getuid()
    run = f"/run/user/{uid}"
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": os.environ.get("HOME", ""),
        "XDG_RUNTIME_DIR": run,
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={run}/bus",
        "LC_ALL": "C.UTF-8",
    }


def run_argv(argv):
    """The real runner: no shell, minimal environment, timeout. Returns text."""
    try:
        done = subprocess.run(argv, shell=False, capture_output=True, text=True,
                              timeout=TIMEOUT_S, env=_env())
    except subprocess.TimeoutExpired:
        return f"ERROR: timed out after {TIMEOUT_S} s"
    except OSError as exc:
        return f"ERROR: {exc.strerror or 'cannot run'}"
    return (done.stdout + done.stderr).strip() or f"(no output, exit {done.returncode})"


def redact(text):
    """Blank lines that look like they carry a secret."""
    out = []
    for line in text.splitlines():
        if SECRET_RE.search(line):
            out.append("[redacted: line looks like a secret]")
        else:
            out.append(line)
    return "\n".join(out)


def _cap(text):
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + "\n[truncated]"
    return text


def _do(argv, runner, secret=False):
    text = runner(argv)
    if secret:
        text = redact(text)
    return _cap(text)


def systemd_cat(unit, runner=run_argv):
    try:
        unit = check_unit(unit)
    except Refused as exc:
        return f"REFUSED: {exc}"
    return _do(["systemctl", "--user", "cat", "--", unit], runner, secret=True)


def systemd_status(pattern="gandalf*", runner=run_argv):
    try:
        pattern = check_pattern(pattern)
    except Refused as exc:
        return f"REFUSED: {exc}"
    if "*" in pattern:
        argv = ["systemctl", "--user", "list-units", "--all", "--no-pager", "--", pattern]
    else:
        argv = ["systemctl", "--user", "status", "--no-pager", "--lines=0", "--", pattern]
    return _do(argv, runner)


def systemd_timers(runner=run_argv):
    return _do(["systemctl", "--user", "list-timers", "--all", "--no-pager"], runner)


def journal_tail(unit, n=50, runner=run_argv):
    try:
        unit = check_unit(unit)
        n = check_lines(n)
    except Refused as exc:
        return f"REFUSED: {exc}"
    argv = ["journalctl", "--user", "-u", unit, "-n", str(n), "--no-pager", "-o", "short-iso"]
    return _do(argv, runner, secret=True)


def tmux_ls(runner=run_argv):
    fmt = "#{session_name} #{session_windows}w created #{session_created_string} attached #{session_attached}"
    return _do(["tmux", "list-sessions", "-F", fmt], runner)
