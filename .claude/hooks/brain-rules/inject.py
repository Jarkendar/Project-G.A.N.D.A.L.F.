#!/usr/bin/env python3
# Injects brain/'s own CLAUDE.md rules into the Claude Code session. brain/ is a
# sibling repo, not part of this project tree, so Claude Code never loads its
# CLAUDE.md files on its own. brain/ is the single source of truth for them —
# this hook only makes them visible, it never copies them anywhere.
#
#   SessionStart          → brain/CLAUDE.md (root rules) + resolved BRAIN_PATH
#   PreToolUse  Write     → CLAUDE.md chain of the target folder, before writing
#   PostToolUse Read/Edit/Glob/Grep → CLAUDE.md chain of the touched folder
#
# Each file is injected at most once per session (state in $TMPDIR). Access via
# Bash (cat, grep) does not trigger this hook. Deterministic, no LLM call; any
# failure is swallowed — this must never block a tool call or a session.

import json
import os
import sys
import tempfile


def read_brain_path(project_dir):
    env_file = os.path.join(project_dir, ".claude", "gandalf.env")
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BRAIN_PATH="):
                    value = line.split("=", 1)[1].strip()
                    return os.path.realpath(os.path.join(project_dir, os.path.expanduser(value)))
    except OSError:
        pass
    return None


def target_path(tool_input):
    for key in ("file_path", "path", "notebook_path"):
        if tool_input.get(key):
            return os.path.realpath(tool_input[key])
    return None


def rule_chain(brain, path):
    """CLAUDE.md files from the brain/ root down to the folder of `path`."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    chain = []
    while folder.startswith(brain):
        candidate = os.path.join(folder, "CLAUDE.md")
        if os.path.isfile(candidate):
            chain.append(candidate)
        if folder == brain:
            break
        folder = os.path.dirname(folder)
    return list(reversed(chain))


def main():
    event = json.load(sys.stdin)
    name = event.get("hook_event_name")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    brain = read_brain_path(project_dir)
    if not brain or not os.path.isdir(brain):
        return

    state_file = os.path.join(
        tempfile.gettempdir(), f"gandalf-brain-rules-{event.get('session_id', 'none')}.json"
    )
    try:
        with open(state_file) as f:
            seen = set(json.load(f))
    except (OSError, ValueError):
        seen = set()

    root_rules = os.path.join(brain, "CLAUDE.md")
    if name == "SessionStart":
        # A new or cleared context: everything must be injected again.
        seen = set()
        files = [root_rules] if os.path.isfile(root_rules) else []
        header = (
            f"BRAIN_PATH resolves to {brain}. The rules below are brain/'s own "
            "CLAUDE.md files, injected by a hook because brain/ lies outside this "
            "project tree. Each brain/ subfolder's CLAUDE.md is injected the first "
            "time a Read/Write/Edit/Glob/Grep touches that folder — access via Bash "
            "does not trigger it, so read the folder's CLAUDE.md explicitly before "
            "writing there with Bash.\n\n"
        )
    else:
        path = target_path(event.get("tool_input") or {})
        if not path or not path.startswith(brain):
            return
        files = [f for f in rule_chain(brain, path) if f not in seen]
        header = ""

    if not files:
        return
    context = header + "\n\n".join(
        f"Contents of {f} (brain/ rules):\n\n{open(f).read()}" for f in files
    )
    seen.update(files)
    with open(state_file, "w") as f:
        json.dump(sorted(seen), f)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": name, "additionalContext": context}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
