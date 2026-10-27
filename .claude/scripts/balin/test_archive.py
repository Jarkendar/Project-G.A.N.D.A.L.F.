#!/usr/bin/env python3
# Cases for archive_transcripts (archive.py), on a throwaway brain/ — never the
# real one.
#
#   python3 .claude/scripts/balin/test_archive.py

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import archive  # noqa: E402

NOW = "2026-10-27T10:00:00"
GEMINI = "Me: Hello, I am working on a project.\nGemini: Great! Tell me more.\nMe: I use uh online first sync.\nGemini: Offline-first, you mean?\n"
CLAUDE = "Me: Cześć — zażółć gęślą jaźń ✓ 日本語\nClaude: Hi.\r\nMe: ok\n"


def item(text, title="Mock call about offline-first", tags=("sync",)):
    return {"title": title, "summary": "The conversation covered sync.", "tags": list(tags), "transcript": text}


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.brain = Path(self._tmp.name)
        (self.brain / "conversations").mkdir()
        self.addCleanup(self._tmp.cleanup)

    def files(self):
        return sorted(p.name for p in (self.brain / "conversations").iterdir())

    def test_layout_hash_and_verbatim(self):
        plan = archive.archive(self.brain, [item(GEMINI)], NOW)
        self.assertEqual(self.files(), ["2026-10-27T10-00-00_agent_mock-call-about-offline-first.md"])
        text = (self.brain / "conversations" / self.files()[0]).read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\ndate: 2026-10-27T10:00:00\nsource: agent\nassistant: gemini\nprivacy: private\n"))
        self.assertIn("tags: [english-review, gemini, sync]\n", text)
        self.assertIn('title: "Mock call about offline-first"\n---\n\n## Summary\n\nThe conversation covered sync.\n\n## Transcript\n\n', text)
        self.assertTrue(text.endswith("## Transcript\n\n" + GEMINI))
        # the same hash the shell would compute (`echo -n "$RAW" | sha256sum`)
        shell = subprocess.run(["sha256sum"], input=GEMINI.encode(), capture_output=True).stdout.split()[0].decode()
        self.assertEqual(plan[0]["content_hash"], "sha256:" + shell)
        self.assertIn(f"content_hash: sha256:{shell}\n", text)

    def test_unicode_and_crlf_kept(self):
        archive.archive(self.brain, [item(CLAUDE, title="Zażółć gęślą — rozmowa")], NOW)
        name = self.files()[0]
        self.assertIn("_agent_zazolc-gesla-rozmowa.md", name)
        with open(self.brain / "conversations" / name, encoding="utf-8", newline="") as fh:
            self.assertTrue(fh.read().endswith("## Transcript\n\n" + CLAUDE))

    def test_several_items_get_plus_one_second_each(self):
        archive.archive(self.brain, [item(GEMINI, "First"), item(CLAUDE, "Second"), item("Me: x\nGemini: y\n", "Third")], "2026-10-27T10:00:58")
        self.assertEqual([n[:19] for n in self.files()], ["2026-10-27T10-00-58", "2026-10-27T10-00-59", "2026-10-27T10-01-00"])

    def test_dedup_against_existing_file_in_ingest_format(self):
        h = "sha256:" + hashlib.sha256(GEMINI.encode()).hexdigest()
        (self.brain / "conversations" / "old.md").write_text(f"---\nsource: bookmarklet\ncontent_hash: {h}\n---\n")
        plan = archive.archive(self.brain, [item(GEMINI)], NOW)
        self.assertEqual(plan[0]["duplicate_of"], "old.md")
        self.assertEqual(self.files(), ["old.md"])

    def test_dedup_survives_a_trailing_newline_difference(self):
        h = "sha256:" + hashlib.sha256(GEMINI.rstrip().encode()).hexdigest()
        (self.brain / "conversations" / "old.md").write_text(f"---\ncontent_hash: {h}\n---\n")
        self.assertEqual(archive.archive(self.brain, [item(GEMINI)], NOW, dry_run=True)[0]["duplicate_of"], "old.md")

    def test_duplicate_inside_one_call(self):
        plan = archive.archive(self.brain, [item(GEMINI, "One"), item(GEMINI, "Two")], NOW)
        self.assertIsNone(plan[0]["duplicate_of"])
        self.assertEqual(plan[1]["duplicate_of"], "item 1 of this call")
        self.assertEqual(len(self.files()), 1)

    def test_dry_run_writes_nothing(self):
        plan = archive.archive(self.brain, [item(GEMINI)], NOW, dry_run=True)
        self.assertEqual(self.files(), [])
        self.assertEqual(plan[0]["lines"], 5)

    def test_never_overwrites(self):
        archive.archive(self.brain, [item(GEMINI)], NOW)
        before = (self.brain / "conversations" / self.files()[0]).read_text(encoding="utf-8")
        with self.assertRaises(archive.Refused):
            archive.archive(self.brain, [item(GEMINI + "Me: more\n")], NOW)  # same name, other content
        self.assertEqual((self.brain / "conversations" / self.files()[0]).read_text(encoding="utf-8"), before)

    def test_whole_or_nothing(self):
        # item 2 collides with an existing file name → nothing of item 1 is written either
        (self.brain / "conversations" / "2026-10-27T10-00-01_agent_second.md").write_text("x")
        with self.assertRaises(archive.Refused):
            archive.archive(self.brain, [item(GEMINI, "First"), item(CLAUDE, "Second")], NOW)
        self.assertEqual(self.files(), ["2026-10-27T10-00-01_agent_second.md"])

    def test_missing_folder_is_not_created(self):
        with self.assertRaises(archive.Refused):
            archive.archive(self.brain / "nowhere", [item(GEMINI)], NOW)
        self.assertFalse((self.brain / "nowhere").exists())

    def test_bad_input_refused(self):
        for bad in (
            [], [item("")], [item(GEMINI, title="")], [item(GEMINI, title="x" * 61)],
            [item(GEMINI, tags=[])], [item(GEMINI, tags=["Bad Tag"])], ["not an object"],
            [{**item(GEMINI), "summary": ""}], [item(GEMINI)] * 11,
        ):
            with self.assertRaises(archive.Refused, msg=repr(bad)[:60]):
                archive.archive(self.brain, bad, NOW)
        with self.assertRaises(archive.Refused):
            archive.archive(self.brain, [item(GEMINI)], "yesterday")
        self.assertEqual(self.files(), [])

    def test_assistant_detection_and_tags(self):
        self.assertEqual(archive.assistant_of("Me: a\nClaude: b\n"), "claude")
        self.assertEqual(archive.assistant_of("Me: a\nGemini: b\nClaude: c\n"), "unknown")
        archive.archive(self.brain, [item("Me: a\nHost: b\n", tags=["a", "b", "c", "d", "e", "f"])], NOW)
        text = (self.brain / "conversations" / self.files()[0]).read_text(encoding="utf-8")
        self.assertIn("assistant: unknown\n", text)
        self.assertIn("tags: [english-review, a, b, c, d, e]\n", text)

    def test_only_conversations_is_touched(self):
        archive.archive(self.brain, [item(GEMINI)], NOW)
        self.assertEqual(sorted(p.name for p in self.brain.iterdir()), ["conversations"])

    def test_long_transcript_round_trip(self):
        long = "".join(f"Me: line {i} zażółć ✓\nGemini: odpowiedź {i}\n" for i in range(5000))
        archive.archive(self.brain, [item(long)], NOW)
        text = (self.brain / "conversations" / self.files()[0]).read_text(encoding="utf-8")
        self.assertTrue(text.endswith("## Transcript\n\n" + long))


if __name__ == "__main__":
    unittest.main()
