#!/usr/bin/env python3
# Write guard for agents. A `PreToolUse` hook on `Write` / `Edit`, declared in
# an agent's own frontmatter, so it binds that agent only. The arguments name
# the places the agent may write a `.md` file to:
#
#   tmp                  the system temp directory (session scratchpad)
#   brain:<subfolder>    a folder under BRAIN_PATH, e.g. brain:knowledge/councils
#
# Anything else is refused (exit 2, reason on stderr). Fails closed: input it
# cannot read, or a BRAIN_PATH it cannot resolve, is a refusal.
#
# N.A.R.V.I. has its own, older guard (.claude/hooks/narvi/) — same rule as
# `guard.py tmp`.

import json
import os
import sys
import tempfile


def refuse(reason):
    print(f"write-guard: {reason}", file=sys.stderr)
    sys.exit(2)


def brain_path(project_dir):
    raw = ""
    try:
        with open(os.path.join(project_dir, ".claude", "gandalf.env")) as fh:
            for line in fh:
                if line.startswith("BRAIN_PATH="):
                    raw = line.split("=", 1)[1].strip().strip("\"'")
    except OSError:
        pass
    raw = os.path.expanduser(raw or "../brain")
    if not os.path.isabs(raw):
        raw = os.path.join(project_dir, raw)
    return os.path.realpath(raw)


def allowed_roots(specs, project_dir):
    roots = []
    for spec in specs:
        if spec == "tmp":
            roots += [os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp")]
        elif spec.startswith("brain:") and spec[6:].strip("/"):
            roots.append(os.path.realpath(os.path.join(brain_path(project_dir), spec[6:].strip("/"))))
        else:
            refuse(f"unknown location '{spec}' in the hook's arguments — write refused")
    return roots


def main():
    try:
        event = json.load(sys.stdin)
        raw = (event.get("tool_input") or {})["file_path"]
    except (ValueError, KeyError, TypeError, AttributeError):
        refuse("could not read the tool input — write refused")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    roots = allowed_roots(sys.argv[1:], project_dir)
    if not roots:
        refuse("no allowed location configured — write refused")
    if not os.path.isabs(raw):
        raw = os.path.join(event.get("cwd") or os.getcwd(), raw)
    path = os.path.realpath(raw)
    if not any(path.startswith(root + os.sep) for root in roots):
        refuse(f"{path} is outside the places this agent may write to ({', '.join(sys.argv[1:])})")
    if not path.endswith(".md"):
        refuse(f"{path} is not a .md file")
    sys.exit(0)


if __name__ == "__main__":
    main()
