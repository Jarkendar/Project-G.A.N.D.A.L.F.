#!/usr/bin/env python3
# Allowed and refused cases for guard.py, run as the hook is run: a subprocess
# with the event on stdin, judged by its exit code. Tokens go to the real
# /tmp/faramir-consent/ and are removed afterwards.
#
#   python3 .claude/hooks/faramir-guard/test_guard.py

import json
import os
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(os.path.realpath("/tmp"), "faramir-consent")
P = "mcp__claude_ai_Google_Calendar__"


def run(tool, tool_input=None, raw=None):
    stdin = raw if raw is not None else json.dumps(
        {"tool_name": tool, "tool_input": tool_input or {}})
    proc = subprocess.run([sys.executable, os.path.join(HERE, "guard.py")],
                          input=stdin, capture_output=True, text=True)
    return proc.returncode, proc.stderr


def token(action, event, body=None, age=0):
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f"{action}-{event}.md")
    with open(path, "w") as fh:
        fh.write(body if body is not None else f"action: {action}\nevent: {event}\n")
    if age:
        old = time.time() - age
        os.utime(path, (old, old))
    return path


class FaramirGuard(unittest.TestCase):
    def tearDown(self):
        if os.path.isdir(DIR):
            for name in os.listdir(DIR):
                if name.endswith(".md") and name.split("-", 1)[0] in ("delete", "update", "respond"):
                    os.remove(os.path.join(DIR, name))

    def refused(self, code, err, msg=""):
        self.assertEqual(code, 2, f"{msg}: {err}")

    def test_reads_and_create_pass(self):
        for tool in ["list_events", "get_event", "list_calendars",
                     "search_events", "suggest_time_periods", "create_event"]:
            self.assertEqual(run(P + tool, {"x": 1})[0], 0, tool)

    def test_other_servers_pass(self):
        self.assertEqual(run("mcp__samwise__search", {})[0], 0)
        self.assertEqual(run("Read", {"file_path": "x"})[0], 0)

    def test_delete_with_token_passes_once(self):
        path = token("delete", "abc123")
        self.assertEqual(run(P + "delete_event", {"eventId": "abc123"})[0], 0)
        self.assertFalse(os.path.exists(path), "token must be consumed")
        self.refused(*run(P + "delete_event", {"eventId": "abc123"}), "second use")

    def test_update_with_token_passes(self):
        token("update", "evt_20261017T080000Z")
        self.assertEqual(run(P + "update_event", {"event_id": "evt_20261017T080000Z"})[0], 0)

    def test_no_token_refused(self):
        self.refused(*run(P + "delete_event", {"eventId": "nope"}), "no token")
        self.refused(*run(P + "update_event", {"eventId": "nope"}), "no token")

    def test_token_for_other_event_or_action(self):
        token("delete", "abc123")
        self.refused(*run(P + "delete_event", {"eventId": "other"}), "other event")
        self.refused(*run(P + "update_event", {"eventId": "abc123"}), "other action")

    def test_expired_token(self):
        token("delete", "old1", age=31 * 60)
        self.refused(*run(P + "delete_event", {"eventId": "old1"}), "expired")

    def test_token_with_wrong_content(self):
        token("delete", "bad1", body="hello\n")
        self.refused(*run(P + "delete_event", {"eventId": "bad1"}), "wrong content")
        token("delete", "bad2", body="action: update\nevent: bad2\n")
        self.refused(*run(P + "delete_event", {"eventId": "bad2"}), "wrong action in file")

    def test_no_or_odd_event_id(self):
        self.refused(*run(P + "delete_event", {}), "no id")
        self.refused(*run(P + "delete_event", {"eventId": "../x"}), "path in id")
        self.refused(*run(P + "delete_event", {"eventId": ["a"]}), "id not a string")

    def test_unknown_connector_tool_refused(self):
        token("respond", "abc123")
        self.refused(*run(P + "respond_to_event", {"eventId": "abc123"}), "respond")
        self.refused(*run(P + "something_new", {}), "unknown")

    def test_router_may_write_the_token(self):
        # The router's own guard (`guard.py gandalf tmp`) must let it write one.
        repo = os.path.realpath(os.path.join(HERE, "..", "..", ".."))
        guard = os.path.join(HERE, "..", "write-guard", "guard.py")
        for name, want in [("delete-abc123.md", 0), ("delete-abc123.json", 2)]:
            event = {"agent_type": "gandalf", "cwd": repo, "tool_name": "Write",
                     "tool_input": {"file_path": os.path.join(DIR, name)}}
            proc = subprocess.run([sys.executable, guard, "gandalf", "tmp"],
                                  input=json.dumps(event), capture_output=True,
                                  text=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=repo))
            self.assertEqual(proc.returncode, want, f"{name}: {proc.stderr}")

    def test_unreadable_input_refused(self):
        self.refused(*run("x", raw="not json"), "bad json")
        self.refused(*run("x", raw="[]"), "not an object")
        self.refused(*run("x", raw="{}"), "no tool name")


if __name__ == "__main__":
    unittest.main()
