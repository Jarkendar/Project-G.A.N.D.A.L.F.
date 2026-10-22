#!/usr/bin/env python3
# Cases for readops.py with an injected runner — no systemd, tmux or journal is
# touched. Also checks that only Aulë's definition names the rpi tools.
#
#   python3 .claude/scripts/rpi/test_readops.py

import json
import os
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import readops  # noqa: E402

REPO = Path(HERE).resolve().parents[2]


class Recorder:
    def __init__(self, out="ok"):
        self.calls = []
        self.out = out

    def __call__(self, argv):
        self.calls.append(argv)
        return self.out


BAD_UNITS = [
    "", "--user", "-x.service", "gandalf restart.service", "gandalf;id.service",
    "gandalf$(id).service", "../gandalf.service", "gandalf/../x.service",
    "ssh.service", "sshd.service", "gandalf", "gandalf.socket", "Gandalf.service",
    "gandalf-" + "a" * 70 + ".service", None, 5, "gandalf.service\n", "gandalf*.service",
]


class Validation(unittest.TestCase):
    def test_good_units(self):
        for u in ("gandalf-restart.service", "gandalf-restart.timer", "samwise-mcp.service"):
            r = Recorder()
            readops.systemd_cat(u, runner=r)
            self.assertEqual(r.calls, [["systemctl", "--user", "cat", "--", u]])

    def test_bad_units_never_run(self):
        for u in BAD_UNITS:
            for fn in (readops.systemd_cat, readops.journal_tail):
                r = Recorder()
                out = fn(u, runner=r)
                self.assertTrue(out.startswith("REFUSED"), (u, out))
                self.assertEqual(r.calls, [], u)

    def test_bad_patterns(self):
        for p in ("", "*", "-a*", "gandalf *", "gandalf;*", "ssh*", "$(id)", None, "../g*"):
            r = Recorder()
            out = readops.systemd_status(p, runner=r)
            self.assertTrue(out.startswith("REFUSED"), (p, out))
            self.assertEqual(r.calls, [])

    def test_status_forms(self):
        r = Recorder()
        readops.systemd_status("gandalf*", runner=r)
        self.assertEqual(r.calls[0][:4], ["systemctl", "--user", "list-units", "--all"])
        r = Recorder()
        readops.systemd_status("gandalf-restart.service", runner=r)
        self.assertIn("--lines=0", r.calls[0])
        self.assertEqual(r.calls[0][-2:], ["--", "gandalf-restart.service"])

    def test_journal_lines(self):
        for n in (0, -1, 201, "5; rm", 5.0, True, None):
            r = Recorder()
            self.assertTrue(readops.journal_tail("gandalf.service", n, runner=r).startswith("REFUSED"), n)
            self.assertEqual(r.calls, [])
        r = Recorder()
        readops.journal_tail("gandalf.service", 200, runner=r)
        self.assertEqual(r.calls[0][:5], ["journalctl", "--user", "-u", "gandalf.service", "-n"])
        self.assertEqual(r.calls[0][5], "200")

    def test_fixed_commands(self):
        r = Recorder()
        readops.systemd_timers(runner=r)
        readops.tmux_ls(runner=r)
        self.assertEqual(r.calls[0], ["systemctl", "--user", "list-timers", "--all", "--no-pager"])
        self.assertEqual(r.calls[1][:2], ["tmux", "list-sessions"])
        for c in r.calls:
            self.assertIsInstance(c, list)
            self.assertNotIn("-S", c)
            self.assertNotIn("-L", c)


class Output(unittest.TestCase):
    def test_secrets_redacted(self):
        r = Recorder("[Service]\nExecStart=/bin/true\nEnvironment=API_TOKEN=abc\nEnvironment=MY_KEY=z\nEnvironment=PASSWORD=p")
        out = readops.systemd_cat("gandalf.service", runner=r)
        self.assertIn("ExecStart=/bin/true", out)
        for s in ("abc", "MY_KEY", "PASSWORD"):
            self.assertNotIn(s, out)
        r = Recorder("Oct 22 secret=hunter2 leaked")
        self.assertNotIn("hunter2", readops.journal_tail("gandalf.service", 5, runner=r))

    def test_truncated(self):
        out = readops.systemd_timers(runner=Recorder("x" * 50_000))
        self.assertLessEqual(len(out), readops.MAX_OUTPUT + 20)
        self.assertTrue(out.endswith("[truncated]"))

    def test_real_runner_no_shell_and_missing_binary(self):
        out = readops.run_argv(["/nonexistent/binary-xyz"])
        self.assertTrue(out.startswith("ERROR"))
        # An argument with shell metacharacters is passed as data, not run.
        out = readops.run_argv(["echo", "a; echo injected"])
        self.assertEqual(out, "a; echo injected")

    def test_env_is_minimal(self):
        env = readops._env()
        self.assertEqual(set(env), {"PATH", "HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "LC_ALL"})


class Scope(unittest.TestCase):
    def test_only_aule_names_the_tools(self):
        for f in (REPO / ".claude" / "agents").glob("*.md"):
            has = "mcp__rpi__" in f.read_text()
            self.assertEqual(has, f.name == "aule.md", f.name)

    def test_settings_allow_exactly_the_five(self):
        text = (REPO / ".claude" / "settings.json").read_text()
        for t in ("systemd_cat", "systemd_status", "systemd_timers", "journal_tail", "tmux_ls"):
            self.assertIn(f'"mcp__rpi__{t}"', text)
        self.assertEqual(text.count("mcp__rpi__"), 5)
        json.loads(text)
        servers = json.loads((REPO / ".mcp.json").read_text())["mcpServers"]
        self.assertIn("rpi", servers)


if __name__ == "__main__":
    unittest.main()
