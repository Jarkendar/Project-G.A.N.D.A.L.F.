#!/usr/bin/env python3
# Write guard for agents. A `PreToolUse` hook on `Write` / `Edit`, declared in
# an agent's own frontmatter. The first argument is that agent's name; the
# rest name the places it may write a `.md` file to:
#
#   guard.py <agent> tmp brain:knowledge/councils
#
#   tmp                  the system temp directory (session scratchpad)
#   brain:<subfolder>    a folder under BRAIN_PATH, e.g. brain:knowledge/councils
#   tmp:<subfolder>      a folder under the system temp directory, e.g.
#                        tmp:gandalf-persona
#   home:<subfolder>     a folder under the user's home, e.g.
#                        home:.local/share/gandalf/personas
#   repo                 this repo (CLAUDE_PROJECT_DIR) — files of any type, not
#                        only `.md`; its `.git/` is always refused
#   !brain:<subfolder>   a folder carved out of the places above — refused even
#                        though a wider place contains it, e.g.
#                        brain:knowledge !brain:knowledge/personas
#
# With `--read` before the places, the same check guards reading instead — a
# `PreToolUse` hook on `Read` / `Grep` / `Glob`: the path read or searched must
# lie in one of the places (the place itself counts), of any file type:
#
#   guard.py aule --read repo
#
# The name matters because a hook in the frontmatter of the agent that runs
# the main thread fires for every sub-agent it spawns as well (seen
# 2026-10-11: the router's guard refused Radagast's report). A call made by
# another agent is passed through here — that agent's own guard decides.
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
        elif spec.startswith("tmp:") and spec[4:].strip("/"):
            sub = spec[4:].strip("/")
            roots += [os.path.realpath(os.path.join(tempfile.gettempdir(), sub)),
                      os.path.realpath(os.path.join("/tmp", sub))]
        elif spec.startswith("home:") and spec[5:].strip("/"):
            roots.append(os.path.realpath(os.path.join(os.path.expanduser("~"), spec[5:].strip("/"))))
        elif spec == "repo":
            roots.append(os.path.realpath(project_dir))
        elif spec.startswith("brain:") and spec[6:].strip("/"):
            roots.append(os.path.realpath(os.path.join(brain_path(project_dir), spec[6:].strip("/"))))
        else:
            refuse(f"unknown location '{spec}' in the hook's arguments — write refused")
    return roots


def inside(path, root):
    return path == root or path.startswith(root + os.sep)


def read_target(tool_name, tool_input):
    # Read names a file; Grep and Glob a folder (the working directory when
    # left out). A Glob pattern may itself reach out — absolute, or with `..`
    # — so its fixed part (before the first wildcard) is checked as well.
    if tool_name == "Read":
        return [tool_input["file_path"]]
    targets = [tool_input.get("path") or "."]
    pattern = tool_input.get("pattern") or ""
    if tool_name == "Glob":
        if ".." in pattern.split("/"):
            refuse(f"the pattern '{pattern}' climbs out with '..' — read refused")
        if os.path.isabs(pattern):
            fixed = pattern.split("*")[0].split("?")[0].split("[")[0].split("{")[0]
            targets.append(fixed or "/")
    return targets


def check_read(event, owner, roots, specs):
    try:
        targets = read_target(event.get("tool_name"), event.get("tool_input") or {})
    except (KeyError, TypeError, AttributeError):
        refuse("could not read the tool input — read refused")
    cwd = event.get("cwd") or os.getcwd()
    for raw in targets:
        path = os.path.realpath(raw if os.path.isabs(raw) else os.path.join(cwd, raw))
        if not any(inside(path, root) for root in roots):
            refuse(f"{path} is outside the places {owner} may read ({', '.join(specs)})")
    sys.exit(0)


def main():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise TypeError
    except (ValueError, TypeError):
        refuse("could not read the tool input — refused")
    if len(sys.argv) < 2:
        refuse("no agent name configured — refused")
    owner, specs = sys.argv[1], sys.argv[2:]
    read_mode = bool(specs) and specs[0] == "--read"
    if read_mode:
        specs = specs[1:]
    caller = event.get("agent_type")
    if caller and caller != owner:
        sys.exit(0)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    roots = allowed_roots([s for s in specs if not s.startswith("!")], project_dir)
    carved = allowed_roots([s[1:] for s in specs if s.startswith("!")], project_dir)
    if not roots:
        refuse("no allowed location configured — refused")
    if read_mode:
        check_read(event, owner, roots, specs)
    try:
        raw = (event.get("tool_input") or {})["file_path"]
    except (KeyError, TypeError, AttributeError):
        refuse("could not read the tool input — write refused")
    if not os.path.isabs(raw):
        raw = os.path.join(event.get("cwd") or os.getcwd(), raw)
    path = os.path.realpath(raw)
    if not any(path.startswith(root + os.sep) for root in roots):
        refuse(f"{path} is outside the places {owner} may write to ({', '.join(specs)})")
    if any(inside(path, root) for root in carved):
        refuse(f"{path} is in a folder {owner} does not write to — it belongs to another agent or skill")
    repo = os.path.realpath(project_dir)
    if "repo" in specs and inside(path, repo):
        if inside(path, os.path.join(repo, ".git")):
            refuse(f"{path} is inside .git/ — git's own files are not written by hand")
        sys.exit(0)
    if not path.endswith(".md"):
        refuse(f"{path} is not a .md file")
    sys.exit(0)


if __name__ == "__main__":
    main()
