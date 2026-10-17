#!/usr/bin/env python3
# Consent guard for F.A.R.A.M.I.R. A `PreToolUse` hook declared in the agent's
# own frontmatter, on every tool of the Google Calendar connector:
#
#   guard.py
#
# Reading, and adding an event with no guests, pass. Deleting, updating, and
# adding an event with guests (the invitation goes out by mail) pass only with
# a token of the owner's consent: the router writes
# `/tmp/faramir-consent/<action>-<key>.md` after the owner's `y` to Faramir's
# plan, holding the lines `action: <action>` and `event: <key>`. Faramir has
# no `Write`, so he cannot make one. A token covers one call (it is removed
# when used) and lapses after 30 minutes.
#
# The key is the event's id for delete and update. A new event has no id yet:
# for `create` it is a fingerprint (16 hex characters of a SHA-256) of the
# title, start, end and the sorted, lower-cased guests. The refusal prints it
# ("odcisk: <key>"), Faramir puts it into his plan, the router writes the token
# on the owner's `y`, Faramir repeats the call unchanged. A changed title, time
# or guest gives another fingerprint and so no consent. Not in the fingerprint:
# description, place, reminders.
#
# Guests are looked for under the field names `attendees`, `guests`, `invitees`,
# `participants`, `attendee_emails`, and under any other key whose name has
# "attend", "guest", "invit" or "particip" in it. A non-empty list is guests;
# a field of any other shape (not a list) is taken to be guests too. A name
# this does not recognise is not found — to be verified against the connector.
#
# Anything under the connector that is not on the lists below — respond to an
# event, a tool added later — is refused: fails closed. So is input it cannot
# read, an event id it cannot find, or one with odd characters.
#
# Refusal: exit 2, reason on stderr.

import hashlib
import json
import os
import re
import sys
import tempfile
import time

PREFIX = "mcp__claude_ai_Google_Calendar__"
PASS = {"list_events", "get_event", "list_calendars", "search_events",
        "suggest_time_periods"}
GUARDED = {"delete_event": "delete", "update_event": "update"}
TTL = 30 * 60
ID_FIELDS = ("eventId", "event_id", "id")
ID_OK = re.compile(r"^[A-Za-z0-9_-]{1,200}$")
GUEST_FIELDS = ("attendees", "guests", "invitees", "participants", "attendee_emails")
GUEST_HINTS = ("attend", "guest", "invit", "particip")


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


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def guests_of(tool_input):
    # The guests the call would invite, canonical; empty when there are none.
    found = []
    for key, value in tool_input.items():
        lowered = key.lower()
        if key not in GUEST_FIELDS and not any(h in lowered for h in GUEST_HINTS):
            continue
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    found.append(item.strip().lower())
                elif isinstance(item, dict) and isinstance(item.get("email"), str):
                    found.append(item["email"].strip().lower())
                else:
                    found.append(canon(item))
        else:
            found.append(canon(value))  # a shape not known: counts as guests
    return sorted(set(found))


def first(tool_input, names):
    for name in names:
        if name in tool_input:
            return tool_input[name]
    return None


def fingerprint(tool_input, guests):
    parts = [
        canon(first(tool_input, ("summary", "title"))),
        canon(first(tool_input, ("start", "startTime", "start_time"))),
        canon(first(tool_input, ("end", "endTime", "end_time"))),
        canon(guests),
    ]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def consumed(action, key):
    for folder in consent_dirs():
        token = os.path.join(folder, f"{action}-{key}.md")
        try:
            if os.path.islink(token) or time.time() - os.path.getmtime(token) > TTL:
                continue
            with open(token) as fh:
                lines = {ln.strip() for ln in fh}
        except OSError:
            continue
        if {f"action: {action}", f"event: {key}"} <= lines:
            try:
                os.remove(token)
            except OSError:
                refuse("the consent token could not be consumed — refused")
            return True
    return False


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
    if tool == "create_event":
        guests = guests_of(tool_input)
        if not guests:
            sys.exit(0)
        key = fingerprint(tool_input, guests)
        if consumed("create", key):
            sys.exit(0)
        refuse(f"no consent of the owner to create an event with guests — odcisk: {key} "
               "— return a PLAN (with this odcisk) to the router and wait for the "
               "owner's y, then repeat the call unchanged")
    action = GUARDED.get(tool)
    if action is None:
        refuse(f"'{tool}' is not a tool Faramir may use — refused")
    event_id = next((tool_input[f] for f in ID_FIELDS if tool_input.get(f)), None)
    if not isinstance(event_id, str) or not ID_OK.match(event_id):
        refuse(f"no usable event id in the {tool} call — refused")
    if consumed(action, event_id):
        sys.exit(0)
    refuse(f"no consent of the owner to {action} event {event_id} — "
           "return a PLAN to the router and wait for the owner's y")


if __name__ == "__main__":
    main()
