"""Hierarchy, line ranges, links and the schema-2 store. No model needed.

Run: python -m unittest discover imladris-rag/tests
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imladris import search, store  # noqa: E402
from imladris.chunking import parse_markdown  # noqa: E402
from imladris.links import Resolver, extract_links  # noqa: E402


def count(text: str) -> int:
    return len(text.split())


DOC = """---
title: Doc
---
# Doc
Intro.

## One
First.

### One A
Deep.

## Two
Second.
"""


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.doc = parse_markdown(Path("d.md"), DOC, count)

    def test_section_numbers_and_paths(self):
        self.assertEqual([(s.path, s.number) for s in self.doc.sections],
                         [([], ""), (["One"], "1"), (["One", "One A"], "1.1"), (["Two"], "2")])

    def test_line_ranges_point_at_the_source(self):
        lines = DOC.splitlines()
        for chunk in self.doc.chunks:
            body_last = chunk.text.splitlines()[-1]
            self.assertEqual(lines[chunk.line_end - 1], body_last)
        one = self.doc.sections[1]
        self.assertEqual(lines[one.line_start - 1], "## One")

    def test_chunks_know_their_section(self):
        self.assertEqual([self.doc.sections[c.section].number for c in self.doc.chunks],
                         ["", "1", "1.1", "2"])

    def test_skip_lines_keep_line_numbers(self):
        doc = parse_markdown(Path("d.md"), DOC.replace("Intro.", "> Source: x\nIntro."), count,
                             {"skip_lines": "^> Source"})
        preamble = doc.chunks[0]
        self.assertTrue(preamble.text.endswith("Intro."))
        self.assertEqual(DOC.replace("Intro.", "> Source: x\nIntro.").splitlines()[preamble.line_end - 1],
                         "Intro.")


class LinksTest(unittest.TestCase):
    def setUp(self):
        self.resolver = Resolver({"core/a.md", "core/b.md", "notes/deep/c.md", "notes/b.md"})

    def test_markdown_relative(self):
        links = extract_links("core/a.md", "see [c](../notes/deep/c.md#part)", self.resolver)
        self.assertEqual([(l.kind, l.target) for l in links], [("markdown", "notes/deep/c.md")])

    def test_urls_and_images_do_not_resolve(self):
        links = extract_links("core/a.md", "[x](https://x.org/a.md) ![i](img.png)", self.resolver)
        self.assertTrue(all(l.target is None for l in links))

    def test_wikilink_unique_and_ambiguous(self):
        self.assertEqual(extract_links("core/a.md", "[[c]]", self.resolver)[0].target, "notes/deep/c.md")
        # two files named b: the one next to the source wins
        self.assertEqual(extract_links("core/a.md", "[[b]]", self.resolver)[0].target, "core/b.md")

    def test_path_mentions_with_foreign_prefix(self):
        links = extract_links("core/a.md", "zob. `brain/notes/deep/c.md` i core/b.md", self.resolver)
        self.assertEqual(sorted(l.target for l in links), ["core/b.md", "notes/deep/c.md"])

    def test_self_link_dropped(self):
        self.assertEqual(extract_links("core/a.md", "core/a.md", self.resolver), [])

    def test_markdown_link_not_double_counted_as_path(self):
        links = extract_links("core/a.md", "[b](core/b.md)", self.resolver)
        self.assertEqual([l.kind for l in links], ["markdown"])


class StoreTest(unittest.TestCase):
    def test_document_tree_roundtrip(self):
        doc = parse_markdown(Path("d.md"), DOC, count)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "i.db"
            conn = store.open_store(db)
            sections = [{"heading": " > ".join(s.path) or "Doc", "section_no": s.number,
                         "line_start": s.line_start, "line_end": s.line_end, "text": s.text}
                        for s in doc.sections]
            blocks = [{"heading": c.heading, "text": c.text, "section": c.section,
                       "line_start": c.line_start, "line_end": c.line_end, "token_count": count(c.text),
                       "vector": np.ones(4, dtype=np.float32).tobytes()} for c in doc.chunks]
            store.write_document(conn, "d.md", content_hash="h", mtime=0.0, indexed_at="now",
                                 title="Doc", frontmatter={"title": "Doc"}, privacy="private",
                                 sections=sections, blocks=blocks,
                                 links=[{"dst": "e.md", "raw": "e.md", "kind": "path", "line": 1}])
            store.set_meta(conn, model_name="m", model_revision="r", embed_dim="4",
                           schema_version=store.SCHEMA_VERSION)
            conn.commit()

            levels = dict(conn.execute("SELECT level, COUNT(*) FROM nodes GROUP BY level").fetchall())
            self.assertEqual(levels, {"doc": 1, "section": 4, "block": 4})
            # every block hangs under the section its chunk came from
            parents = conn.execute(
                "SELECT s.section_no FROM nodes b JOIN nodes s ON b.parent_id = s.id "
                "WHERE b.level = 'block' ORDER BY b.ord").fetchall()
            self.assertEqual([p[0] for p in parents], ["", "1", "1.1", "2"])
            conn.close()

            idx = search.load_index(db)
            self.assertEqual(len(idx.texts), 4)
            self.assertEqual(idx.section_nos, ["", "1", "1.1", "2"])

            conn = store.open_store(db)
            store.delete_document(conn, "d.md")
            conn.commit()
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM links").fetchone()[0], 0)

    def test_schema1_index_is_left_alone_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            old = sqlite3.connect(db)
            old.executescript("CREATE TABLE chunks (id INTEGER); CREATE TABLE meta (key TEXT, value TEXT);"
                              "INSERT INTO meta VALUES ('model_name', 'm'), ('schema_version', '1');")
            old.commit()
            old.close()
            conn = store.open_store(db)
            with self.assertRaises(store.IndexMismatch):
                store.check_consistency(conn, "m", "main", "v2")
            self.assertEqual(store.stored_hashes(conn), {})


if __name__ == "__main__":
    unittest.main()
