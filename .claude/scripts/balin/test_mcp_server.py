#!/usr/bin/env python3
# The MCP wrapper of archive_transcripts on a throwaway brain/. Needs the MCP SDK
# (the Gimli venv): run from another Python, the test starts itself again under it.
#
#   python3 .claude/scripts/balin/test_mcp_server.py

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, "..", "gimli", ".venv", "bin", "python")

try:
    import mcp  # noqa: F401
except ImportError:
    if os.path.exists(VENV) and not os.environ.get("BALIN_TEST_REEXEC"):
        os.environ["BALIN_TEST_REEXEC"] = "1"
        os.execv(VENV, [VENV, *sys.argv])
    raise

import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, HERE)
import mcp_server  # noqa: E402

ITEM = {"title": "T one", "summary": "s", "tags": ["x"], "transcript": "Me: a\nGemini: b\n"}


class WrapperTest(unittest.TestCase):
    def test_dry_run_then_write_then_duplicate_then_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            brain = Path(tmp)
            (brain / "conversations").mkdir()
            with mock.patch.object(mcp_server, "_brain", return_value=brain):
                dry = mcp_server.archive_transcripts([ITEM], "2026-10-27T10:00:00", True)
                self.assertIn("would archive 1 of 1", dry)
                self.assertEqual(list((brain / "conversations").iterdir()), [])
                done = mcp_server.archive_transcripts([ITEM], "2026-10-27T10:00:00")
                self.assertIn("archived 1 of 1", done)
                self.assertIn("conversations/2026-10-27T10-00-00_agent_t-one.md", done)
                again = mcp_server.archive_transcripts([ITEM], "2026-10-27T10:05:00")
                self.assertIn("DUPLICATE", again)
                self.assertTrue(mcp_server.archive_transcripts([], "x").startswith("BALIN: refused"))
                self.assertEqual(len(list((brain / "conversations").iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
