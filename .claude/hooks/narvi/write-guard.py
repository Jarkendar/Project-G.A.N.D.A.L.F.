#!/usr/bin/env python3
# N.A.R.V.I.'s write guard. A `PreToolUse` hook on `Write`, declared in the
# agent's own frontmatter (.claude/agents/narvi.md), so it binds that
# sub-agent only. A draft digest belongs in the session scratchpad: the write
# is let through only for a `.md` file under the system temp directory, and
# refused (exit 2, reason on stderr) anywhere else — brain/, this repo, home.
#
# Fails closed: input it cannot read is a refusal.

import json
import os
import sys
import tempfile

ALLOWED_ROOTS = {os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp")}


def refuse(reason):
    print(f"NARVI write-guard: {reason}", file=sys.stderr)
    sys.exit(2)


def main():
    try:
        event = json.load(sys.stdin)
        raw = (event.get("tool_input") or {})["file_path"]
    except (ValueError, KeyError, TypeError, AttributeError):
        refuse("could not read the tool input — write refused")
    if not os.path.isabs(raw):
        raw = os.path.join(event.get("cwd") or os.getcwd(), raw)
    path = os.path.realpath(raw)
    if not any(path.startswith(root + os.sep) for root in ALLOWED_ROOTS):
        refuse(
            f"{path} is outside the scratchpad. Drafts go to the `draft_file` the caller "
            "gave you (under the system temp directory); nothing is written to brain/ or the repo."
        )
    if not path.endswith(".md"):
        refuse(f"{path} is not a .md draft")
    sys.exit(0)


if __name__ == "__main__":
    main()
