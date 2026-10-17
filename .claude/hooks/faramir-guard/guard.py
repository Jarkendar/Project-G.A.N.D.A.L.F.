#!/usr/bin/env python3
# Consent guard for F.A.R.A.M.I.R. A `PreToolUse` hook declared in the agent's
# own frontmatter, on every tool of the Google Calendar connector:
#
#   guard.py
#
# Reading and adding an event pass. Deleting and updating one pass only with
# a token of the owner's consent: the router writes
# `/tmp/faramir-consent/<action>-<event id>.md` after the owner's `y` to
# Faramir's plan, holding the lines `action: <action>` and `event: <event id>`.
# Faramir has no `Write`, so he cannot make one. A token covers one call (it is
# removed when used) and lapses after 30 minutes.
#
# Anything under the connector that is not on the lists below — respond to an
# event, a tool added later — is refused: fails closed. So is input it cannot
# read, an event id it cannot find, or one with odd characters.
#
# Not covered: `create_event` with guests (the invitation goes out) — that is
# held back by the agent's own instructions only.
#
# Refusal: exit 2, reason on stderr.

import json
import os
import re
import sys
import tempfile
import time

PREFIX = "mcp__claude_ai_Google_Calendar__"
PASS = {"list_events", "get_event", "list_calendars", "search_events",
        "suggest_time_periods", "create_event"}
GUARDED = {"delete_event": "delete", "update_event": "update"}
TTL = 30 * 60
ID_FIELDS = ("eventId", "event_id", "id")
ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


def refuse(reason):
    print(f"faramir-guard: {reason}", file=sys.stderr)
    sys.exit(2)


def consent_dirs():
    dirs = []
    for base in ("/tmp", tempfile.gettempdir()):
        path = os.path.join(os.path.realpath(base), "faramir-consent")
        if path not in dirs:
            dirs.append(path)
    return dirs


def main():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise TypeError
        name = event["tool_name"]
        tool_input = event.get("tool_input") or {}
        if not isinstance(name, str) or not isinstance(tool_input, dict):
            raise TypeError
    except (ValueError, TypeError, KeyError):
        refuse("could not read the tool input — refused")
    if not name.startswith(PREFIX):
        sys.exit(0)  # not a calendar tool: not this guard's business
    tool = name[len(PREFIX):]
    if tool in PASS:
        sys.exit(0)
    action = GUARDED.get(tool)
    if action is None:
        refuse(f"'{tool}' is not a tool Faramir may use — refused")
    event_id = next((tool_input[f] for f in ID_FIELDS if tool_input.get(f)), None)
    if not isinstance(event_id, str) or not ID_OK.match(event_id):
        refuse(f"no usable event id in the {tool} call — refused")
    for folder in consent_dirs():
        token = os.path.join(folder, f"{action}-{event_id}.md")
        try:
            if os.path.islink(token) or time.time() - os.path.getmtime(token) > TTL:
                continue
            with open(token) as fh:
                lines = {ln.strip() for ln in fh}
        except OSError:
            continue
        if {f"action: {action}", f"event: {event_id}"} <= lines:
            try:
                os.remove(token)
            except OSError:
                refuse("the consent token could not be consumed — refused")
            sys.exit(0)
    refuse(f"no consent of the owner to {action} event {event_id} — "
           "return a PLAN to the router and wait for the owner's y")


if __name__ == "__main__":
    main()
