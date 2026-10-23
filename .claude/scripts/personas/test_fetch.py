#!/usr/bin/env python3
# fetch.py gives every catalog row a `file` (the digest's file name) that
# assemble.py requires. Run: python3 .claude/scripts/personas/test_fetch.py
# No network and no brain/: download, the cache and the source list are stand-ins.

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

PARENT_TEXT = "MEMO ONE\nfirst body\nMEMO TWO\nsecond body\n"


class FileField(unittest.TestCase):
    def run_fetch(self, sources):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "sources.json").write_text(json.dumps(sources))
            with mock.patch.object(fetch, "cache_dir", lambda slug: tmp / "cache"), \
                 mock.patch.object(fetch, "persona_dir", lambda slug: tmp / "none"), \
                 mock.patch.object(fetch, "download", lambda url: (PARENT_TEXT.encode(), "text/plain")), \
                 mock.patch.object(fetch.time, "sleep", lambda s: None), \
                 mock.patch.object(sys, "argv", ["fetch.py", "x", "--sources", str(tmp / "sources.json")]):
                self.assertEqual(fetch.main(), 0)
            return {r["id"]: r for r in json.loads((tmp / "cache" / "catalog.json").read_text())}

    def test_default_and_explicit_file(self):
        rows = self.run_fetch([
            {"id": "a", "url": "https://x.y/a"},
            {"id": "b", "url": "https://x.y/b", "file": "custom.md"},
        ])
        self.assertEqual(rows["a"]["file"], "a.md")
        self.assertEqual(rows["b"]["file"], "custom.md")

    def test_excerpts_get_file(self):
        rows = self.run_fetch([
            {"id": "coll", "url": "https://x.y/c", "collection": True},
            {"id": "m1", "from": "coll", "start": "^MEMO ONE"},
            {"id": "m2", "from": "coll", "start": "^MEMO TWO", "file": "two.md"},
        ])
        self.assertEqual(rows["m1"]["file"], "m1.md")
        self.assertEqual(rows["m2"]["file"], "two.md")


if __name__ == "__main__":
    unittest.main()
