"""Chunker and corpus tests. No model needed: token counts come from a
word-count stand-in, which is all the chunkers need from `count`.

Run: python -m unittest discover imladris-rag/tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imladris.chunking import (  # noqa: E402
    chunk_markdown_v1, chunk_markdown_v2, split_frontmatter, split_oversize, split_sections,
)
from imladris.corpus import Corpus  # noqa: E402


def count(text: str) -> int:
    return len(text.split())


DOC = """---
title: Doc Title
tags: [a]
---
# Doc Title (long form)
> Source: somewhere
Intro line.

## Alpha
Alpha paragraph one.

Alpha paragraph two.

### Alpha Sub
Deep text.

## Beta
Beta text.
"""


class FrontmatterTest(unittest.TestCase):
    def test_splits_fields_and_body(self):
        fm, body = split_frontmatter(DOC)
        self.assertEqual(fm["title"], "Doc Title")
        self.assertTrue(body.startswith("# Doc Title"))

    def test_no_frontmatter(self):
        self.assertEqual(split_frontmatter("plain"), ({}, "plain"))


class SectionsTest(unittest.TestCase):
    def test_heading_paths_and_first_h1_dropped(self):
        _, body = split_frontmatter(DOC)
        paths = [path for path, _ in split_sections(body)]
        self.assertEqual(paths, [[], ["Alpha"], ["Alpha", "Alpha Sub"], ["Beta"]])


class ChunkerV2Test(unittest.TestCase):
    def test_title_and_path_prefix(self):
        chunks = chunk_markdown_v2(Path("d.md"), DOC, count)
        headings = [h for h, _ in chunks]
        self.assertEqual(headings, ["Doc Title", "Alpha", "Alpha > Alpha Sub", "Beta"])
        self.assertTrue(chunks[2][1].startswith("Doc Title\nAlpha > Alpha Sub\n\nDeep text."))

    def test_blocks_of_a_section_are_packed_together(self):
        alpha = dict(chunk_markdown_v2(Path("d.md"), DOC, count))["Alpha"]
        self.assertIn("Alpha paragraph one.\n\nAlpha paragraph two.", alpha)

    def test_small_target_splits_between_blocks_not_inside(self):
        # the target has a 32-token floor, so the blocks must be bigger than that
        one, two = " ".join(["one"] * 25), " ".join(["two"] * 25)
        doc = f"---\ntitle: T\n---\n## Alpha\n{one}\n\n{two}\n"
        alpha = [t for h, t in chunk_markdown_v2(Path("d.md"), doc, count, {"target": 40}) if h == "Alpha"]
        self.assertEqual(alpha, [f"T\nAlpha\n\n{one}", f"T\nAlpha\n\n{two}"])

    def test_skip_lines(self):
        texts = "".join(t for _, t in chunk_markdown_v2(Path("d.md"), DOC, count, {"skip_lines": "^> Source"}))
        self.assertNotIn("Source: somewhere", texts)

    def test_prefix_none(self):
        chunks = chunk_markdown_v2(Path("d.md"), DOC, count, {"prefix": "none"})
        self.assertTrue(dict(chunks)["Beta"].startswith("Beta text."))

    def test_merge_tiny_folds_into_neighbour(self):
        chunks = chunk_markdown_v2(Path("d.md"), DOC, count, {"merge_tiny": 3})
        self.assertLess(len(chunks), 4)


class OversizeTest(unittest.TestCase):
    def test_table_split_repeats_header(self):
        table = "| a | b |\n|---|---|\n" + "\n".join(f"| {i} | row{i} |" for i in range(10))
        pieces = split_oversize(table, budget=20, count=count)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all(p.startswith("| a | b |\n|---|---|") for p in pieces))

    def test_prose_split_on_sentences(self):
        prose = "One two three. Four five six. Seven eight nine."
        self.assertEqual(split_oversize(prose, budget=4, count=count),
                         ["One two three.", "Four five six.", "Seven eight nine."])


class ChunkerV1Test(unittest.TestCase):
    def test_windows_carry_title_and_heading(self):
        chunks = chunk_markdown_v1(Path("d.md"), DOC)
        self.assertIn(("Beta", "Doc Title\nBeta\n\nBeta text."), chunks)


class CorpusTest(unittest.TestCase):
    def test_exclusion_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("keep.md", "notes/keep2.md", "index/skip.md", "logs/raw/skip.md",
                        "notes/CLAUDE.md", "notes/image.png"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("x")
            corpus = Corpus(root=root, exclude_top_dirs=frozenset({"index"}),
                            exclude_prefixes=("logs/raw",), exclude_names=frozenset({"CLAUDE.md"}))
            self.assertEqual([p.as_posix() for p in corpus.discover()], ["keep.md", "notes/keep2.md"])
            self.assertEqual([p.as_posix() for p in corpus.discover(root / "notes")], ["notes/keep2.md"])


if __name__ == "__main__":
    unittest.main()
