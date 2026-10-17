#!/usr/bin/env python3
# Cases for the optional `date` of Ori's `commit`, on a throwaway repository
# (a bare origin and a clone on main) — never on the real brain/.
#
#   python3 .claude/scripts/ori/test_commit_date.py
#
# The server needs the MCP SDK, which lives in the Gimli venv: run from another
# Python, the test starts itself again under that one.

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, "..", "gimli", ".venv", "bin", "python")

try:
    import mcp  # noqa: F401
except ImportError:
    if os.path.exists(VENV) and not os.environ.get("ORI_TEST_REEXEC"):
        os.environ["ORI_TEST_REEXEC"] = "1"
        os.execv(VENV, [VENV, *sys.argv])
    raise

import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, HERE)
import mcp_server  # noqa: E402

IDENT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
         "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
SUBJECT = "feat(daily): process 2026-10-16 — a day"


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, env={**os.environ, **IDENT})


class CommitDate(unittest.TestCase):
    def setUp(self):
        self.saved_env = {k: os.environ.get(k) for k in IDENT}
        os.environ.update(IDENT)
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.origin = os.path.join(root, "origin.git")
        self.repo = os.path.join(root, "brain")
        sh(root, "git", "init", "--bare", "-b", "main", self.origin)
        sh(root, "git", "clone", self.origin, self.repo)
        sh(self.repo, "git", "checkout", "-b", "main")
        self.write("seed.md", "seed")
        sh(self.repo, "git", "add", "seed.md")
        sh(self.repo, "git", "commit", "-m", "seed")
        sh(self.repo, "git", "push", "-u", "origin", "main")
        self.real_brain, self.real_now = mcp_server._brain, mcp_server._now
        mcp_server._brain = lambda: Path(self.repo).resolve()
        self.now = datetime.now().astimezone().replace(hour=15, minute=30, second=0, microsecond=0)
        mcp_server._now = lambda: self.now

    def tearDown(self):
        mcp_server._brain, mcp_server._now = self.real_brain, self.real_now
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def write(self, name, text):
        with open(os.path.join(self.repo, name), "w") as fh:
            fh.write(text)

    def dates(self, ref="HEAD"):
        out = subprocess.run(["git", "-C", self.repo, "log", "-1", "--format=%aI%n%cI", ref],
                             capture_output=True, text=True).stdout.split()
        return out

    def head(self, ref="HEAD"):
        return subprocess.run(["git", "-C", self.repo, "rev-parse", ref],
                              capture_output=True, text=True).stdout.strip()

    def day(self, back):
        return (self.now.date() - timedelta(days=back)).isoformat()

    def commit(self, date, name="n.md"):
        self.write(name, "x" + str(date))
        return mcp_server.commit([name], SUBJECT, date)

    def test_yesterday_is_noon_local_for_author_and_committer(self):
        out = self.commit(self.day(1))
        self.assertIn("committed and pushed", out)
        self.assertIn(f"(dated {self.day(1)}T12:00:00", out)
        author, committer = self.dates()
        self.assertEqual(author, committer)
        parsed = datetime.fromisoformat(author)
        self.assertEqual(parsed.date().isoformat(), self.day(1))
        self.assertEqual(parsed.hour, 12)
        self.assertEqual(parsed.utcoffset(), datetime.combine(parsed.date(), parsed.time()).astimezone().utcoffset())

    def test_the_dated_commit_reaches_the_remote(self):
        self.commit(self.day(1))
        self.assertEqual(self.head(), self.head("origin/main"))
        remote = subprocess.run(["git", "-C", self.origin, "log", "-1", "--format=%aI", "main"],
                                capture_output=True, text=True).stdout.strip()
        self.assertTrue(remote.startswith(self.day(1)))

    def test_trailer_and_subject_untouched(self):
        self.commit(self.day(1))
        body = subprocess.run(["git", "-C", self.repo, "log", "-1", "--format=%B"],
                              capture_output=True, text=True).stdout
        self.assertTrue(body.startswith(SUBJECT))
        self.assertIn("Co-Authored-By: Claude <noreply@anthropic.com>", body)

    def test_seven_days_back_passes_eight_does_not(self):
        self.assertIn("committed and pushed", self.commit(self.day(7), "a.md"))
        before = self.head()
        out = self.commit(self.day(8), "b.md")
        self.assertIn("refused", out)
        self.assertIn("7 days", out)
        self.assertEqual(self.head(), before)

    def test_today_uses_the_clock_not_noon(self):
        out = self.commit(self.day(0))
        self.assertIn(f"(dated {self.day(0)}T15:30:00", out)

    def test_future_refused_and_nothing_changed(self):
        before = self.head()
        out = self.commit(self.day(-1))
        self.assertIn("future", out)
        self.assertEqual(self.head(), before)
        status = subprocess.run(["git", "-C", self.repo, "diff", "--cached", "--name-only"],
                                capture_output=True, text=True).stdout
        self.assertEqual(status.strip(), "")  # nothing was staged

    def test_bad_formats_refused(self):
        before = self.head()
        for bad in ["16-10-2026", "2026-10-16T12:00:00", "2026-10-16; touch x", "", " 2026-10-16",
                    "2026-10-16\n", "2026-02-30", "2026-13-01", "today", 20261016, ["2026-10-16"]]:
            out = self.commit(bad)
            self.assertIn("refused", out, repr(bad))
        self.assertEqual(self.head(), before)

    def test_no_date_means_now_and_nothing_leaks(self):
        self.commit(self.day(1), "a.md")
        mcp_server._now = self.real_now
        self.write("b.md", "b")
        out = mcp_server.commit(["b.md"], SUBJECT)
        self.assertNotIn("dated", out)
        author, committer = self.dates()
        self.assertLess(abs(datetime.now().astimezone() - datetime.fromisoformat(author)), timedelta(minutes=2))
        self.assertLess(abs(datetime.now().astimezone() - datetime.fromisoformat(committer)), timedelta(minutes=2))
        self.assertNotIn("GIT_AUTHOR_DATE", os.environ)

    def test_other_refusals_still_hold_with_a_date(self):
        sh(self.repo, "git", "checkout", "-b", "feat/x")
        self.write("n.md", "x")
        self.assertIn("not main", mcp_server.commit(["n.md"], SUBJECT, self.day(1)))
        sh(self.repo, "git", "checkout", "main")
        self.assertIn("refused", mcp_server.commit(["n.md"], "no conventional subject", self.day(1)))

    def test_dst_boundary_day_still_noon(self):
        # Whatever the zone, a fixed day gives noon local time with a valid offset.
        for back in range(1, 8):
            stamp = mcp_server._commit_date(self.day(back))
            self.assertTrue(stamp.startswith(self.day(back) + "T12:00:00"), stamp)


class Handshake(unittest.TestCase):
    def test_commit_lists_date_parameter(self):
        import asyncio
        tools = asyncio.run(mcp_server.server.list_tools())
        commit = next(t for t in tools if t.name == "commit")
        props = commit.input_schema["properties"]
        self.assertIn("date", props)
        self.assertNotIn("date", commit.input_schema.get("required", []))


if __name__ == "__main__":
    unittest.main()
