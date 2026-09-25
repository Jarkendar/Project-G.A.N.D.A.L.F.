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


class SearchHelpersTest(unittest.TestCase):
    def test_load_stopwords(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "stop.txt"
            f.write_text("# comment\nThe\n\nand  # trailing\n")
            self.assertEqual(search.load_stopwords(f), frozenset({"the", "and"}))

    def test_fts_query_stems_and_drops_stopwords(self):
        stop = frozenset({"jest"})
        self.assertEqual(search.fts_query("kto jest uposażonym w polisie", 5, stop), '"kto" OR "uposa"* OR "polis"*')
        self.assertIn('"jest"', search.fts_query("kto jest", 5))  # the engine ships no stopwords
        self.assertEqual(search.fts_query("polisie", 0), '"polisie"')

    def test_diversify_keeps_best_block_per_file(self):
        hits = [{"path": "a"}, {"path": "a"}, {"path": "b"}, {"path": "c"}]
        self.assertEqual([h["path"] for h in search.diversify(hits, 2)], ["a", "b"])


class StoreBackend:
    """Where a test's index lives; subclasses switch the backend."""
    keyword_search = True

    def location(self, tmp):
        return Path(tmp) / "i.db"


class ContextTest(StoreBackend, unittest.TestCase):
    """build_context over a two-file store, with the query embedding faked."""

    def test_bundle_widens_hits_and_respects_budget(self):
        from unittest import mock
        from imladris import context
        with tempfile.TemporaryDirectory() as tmp:
            db = self.location(tmp)
            st = store.open_store(db)
            for path, axis in (("a.md", 0), ("b.md", 1)):
                doc = parse_markdown(Path(path), DOC, count)
                sections = [{"heading": " > ".join(s.path) or "Doc", "section_no": s.number,
                             "line_start": s.line_start, "line_end": s.line_end, "text": s.text}
                            for s in doc.sections]
                blocks = []
                for n, c in enumerate(doc.chunks):
                    vec = np.zeros(4, dtype=np.float32)
                    vec[axis] = 1.0 - 0.1 * n            # a.md along x, b.md along y; earlier blocks score higher
                    vec[2] = 0.1 * n
                    vec /= np.linalg.norm(vec)
                    blocks.append({"heading": c.heading, "text": c.text, "section": c.section,
                                   "line_start": c.line_start, "line_end": c.line_end,
                                   "token_count": count(c.text), "vector": vec.tobytes()})
                st.write_document(path, content_hash="h", mtime=0.0, indexed_at="now", title="Doc",
                                  frontmatter={}, privacy="private", sections=sections, blocks=blocks,
                                  links=[])
            st.set_meta(model_name="m", model_revision="r", embed_dim="4",
                        schema_version=store.SCHEMA_VERSION)
            st.commit()
            st.close()

            idx = search.load_index(db)
            query = np.array([0.9, 0.44, 0.0, 0.0], dtype=np.float32)
            with mock.patch.object(context, "embed_query", return_value=query / np.linalg.norm(query)):
                items = context.build_context(idx, "q", count, budget=1000, lead_files=2, doc_max=5)
                self.assertEqual([it.path for it in items[:2]], ["a.md", "b.md"])  # both lead files first
                self.assertTrue(all(it.kind == "section" for it in items))       # short sections widened
                self.assertEqual(len({(it.path, it.section_no) for it in items}), len(items))  # no repeats
                tight = context.build_context(idx, "q", count, budget=4, lead_files=2, doc_max=5)
                self.assertLessEqual(sum(it.tokens for it in tight), 4)

    def test_zmax_lets_a_document_vector_lead(self):
        from unittest import mock
        from imladris import context

        def at(cos):  # a unit vector with this cosine to the query (x axis)
            return np.array([cos, np.sqrt(1 - cos * cos), 0, 0], dtype=np.float32).tobytes()

        with tempfile.TemporaryDirectory() as tmp:
            db = self.location(tmp)
            st = store.open_store(db)
            # c.md's block barely matches, but its summary names the category
            for path, block_cos, doc_cos in (("a.md", 0.9, 0.1), ("b.md", 0.5, 0.1), ("c.md", 0.1, 0.9)):
                st.write_document(path, content_hash="h", mtime=0.0, indexed_at="now", title=path,
                                  frontmatter={}, privacy="public",
                                  sections=[{"heading": path, "section_no": "", "line_start": 1,
                                             "line_end": 1, "text": "x"}],
                                  blocks=[{"heading": path, "text": "x", "section": 0, "line_start": 1,
                                           "line_end": 1, "token_count": 1, "vector": at(block_cos)}],
                                  links=[], doc_text=f"{path} summary", doc_vector=at(doc_cos))
            st.set_meta(model_name="m", model_revision="r", embed_dim="4",
                        schema_version=store.SCHEMA_VERSION)
            st.commit()
            st.close()

            idx = search.load_index(db)
            self.assertEqual(idx.doc_paths, ["a.md", "b.md", "c.md"])
            with mock.patch.object(context, "embed_query", return_value=np.array([1, 0, 0, 0], dtype=np.float32)):
                lead = lambda rank: context.build_context(idx, "q", count, lead_files=1, links=False,
                                                          file_rank=rank)[0].path
                self.assertEqual(lead("blocks"), "a.md")
                self.assertEqual(lead("zmax"), "c.md")
                with self.assertRaises(ValueError):
                    lead("max")


class StoreTest(StoreBackend, unittest.TestCase):
    def test_document_tree_roundtrip(self):
        doc = parse_markdown(Path("d.md"), DOC, count)
        with tempfile.TemporaryDirectory() as tmp:
            db = self.location(tmp)
            st = store.open_store(db)
            sections = [{"heading": " > ".join(s.path) or "Doc", "section_no": s.number,
                         "line_start": s.line_start, "line_end": s.line_end, "text": s.text}
                        for s in doc.sections]
            blocks = [{"heading": c.heading, "text": c.text, "section": c.section,
                       "line_start": c.line_start, "line_end": c.line_end, "token_count": count(c.text),
                       "vector": np.ones(4, dtype=np.float32).tobytes()} for c in doc.chunks]
            st.write_document("d.md", content_hash="h", mtime=0.0, indexed_at="now",
                              title="Doc", frontmatter={"title": "Doc"}, privacy="private",
                              sections=sections, blocks=blocks,
                              links=[{"dst": "e.md", "raw": "e.md", "kind": "path", "line": 1}])
            st.set_meta(model_name="m", model_revision="r", embed_dim="4",
                        schema_version=store.SCHEMA_VERSION)
            st.commit()

            title, privacy, sections, blocks = st.document("d.md")
            self.assertEqual((title, privacy, len(sections), len(blocks)), ("Doc", "private", 4, 4))
            # every block hangs under the section its chunk came from
            self.assertEqual([sections[b[1]][0] for b in blocks], ["", "1", "1.1", "2"])
            self.assertEqual(st.neighbours("d.md"), {"e.md"})
            self.assertEqual(st.neighbours("e.md"), {"d.md"})
            st.close()

            idx = search.load_index(db)
            self.assertEqual(len(idx.texts), 4)
            self.assertEqual(idx.section_nos, ["", "1", "1.1", "2"])
            if self.keyword_search:
                # full text: backfilled blocks are searchable; "Dee" prefix-matches "Deep"
                hits = search.fts_search(idx, "Deeper things", top_k=3, stem=3)
                self.assertEqual([h["section_no"] for h in hits], ["1.1"])
            idx.store.close()

            st = store.open_store(db)
            st.delete_document("d.md")
            st.commit()
            self.assertEqual((st.stored_hashes(), st.blocks(), st.neighbours("e.md")), ({}, [], set()))


class SqliteOnlyTest(unittest.TestCase):
    def test_schema1_index_is_left_alone_and_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "old.db"
            old = sqlite3.connect(db)
            old.executescript("CREATE TABLE chunks (id INTEGER); CREATE TABLE meta (key TEXT, value TEXT);"
                              "INSERT INTO meta VALUES ('model_name', 'm'), ('schema_version', '1');")
            old.commit()
            old.close()
            st = store.open_store(db)
            with self.assertRaises(store.IndexMismatch):
                st.check_consistency("m", "main", "v2")
            self.assertEqual(st.stored_hashes(), {})


QDRANT_URL = "http://127.0.0.1:6333"


class QdrantBackend(StoreBackend):
    """The same tests against a Qdrant server; skipped when none is running.
    Each test gets a throwaway collection."""
    keyword_search = False  # sparse BM25 arrives in Stage 3, Q4

    def setUp(self):
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(url=QDRANT_URL, timeout=2)
            self.client.get_collections()
        except Exception as err:  # no extra installed, or no server
            self.skipTest(f"no Qdrant at {QDRANT_URL}: {err}")
        self.collections = []

    def tearDown(self):
        for name in self.collections:
            self.client.delete_collection(name)
        self.client.close()

    def location(self, tmp):
        import uuid
        self.collections.append(f"imladris_test_{uuid.uuid4().hex[:8]}")
        return f"{QDRANT_URL}/{self.collections[-1]}"


class QdrantContextTest(QdrantBackend, ContextTest):
    pass


class QdrantStoreTest(QdrantBackend, StoreTest):
    pass



class QdrantCopyTest(QdrantBackend, unittest.TestCase):
    def test_copy_from_sqlite_keeps_the_index(self):
        # normalized, as the store expects: Qdrant's cosine space normalizes on write
        unit = lambda v: (np.array(v, dtype=np.float32) / np.linalg.norm(v)).astype(np.float32).tobytes()
        doc = parse_markdown(Path("d.md"), DOC, count)
        sections = [{"heading": " > ".join(s.path) or "Doc", "section_no": s.number,
                     "line_start": s.line_start, "line_end": s.line_end, "text": s.text} for s in doc.sections]
        with tempfile.TemporaryDirectory() as tmp:
            src = store.open_store(Path(tmp) / "i.db")
            for n, path in enumerate(("d.md", "e.md")):
                blocks = [{"heading": c.heading, "text": c.text, "section": c.section, "line_start": c.line_start,
                           "line_end": c.line_end, "token_count": count(c.text),
                           "vector": unit([n + 1, i + 1, 0, 1])}
                          for i, c in enumerate(doc.chunks)]
                src.write_document(path, content_hash=f"h{n}", mtime=0.0, indexed_at="now", title=path,
                                   frontmatter={"title": path}, privacy="public", sections=sections, blocks=blocks,
                                   links=[{"dst": "e.md", "raw": "e.md", "kind": "path", "line": 1}],
                                   doc_text=f"{path} summary" if n else None,
                                   doc_vector=unit([1, 1, 1, 1]) if n else None)
            src.set_meta(model_name="m", model_revision="r", embed_dim="4", schema_version=store.SCHEMA_VERSION)
            src.commit()

            dst = store.open_store(self.location(tmp))
            self.assertEqual(store.copy_store(src, dst, log=lambda _: None), 2)
            self.assertEqual(dst.stored_hashes(), src.stored_hashes())
            self.assertEqual(dst.get_meta()["model_name"], "m")
            self.assertEqual(dst.doc_vectors(), src.doc_vectors())
            strip = lambda rows: [{k: v for k, v in r.items() if k != "id"} for r in rows]
            self.assertEqual(strip(dst.blocks()), strip(src.blocks()))
            for path in ("d.md", "e.md"):
                title, privacy, sections_src, blocks_src = src.document(path)
                self.assertEqual(dst.document(path)[:2], (title, privacy))
                self.assertEqual(list(dst.document(path)[2].values()), list(sections_src.values()))
                self.assertEqual(dst.neighbours(path), src.neighbours(path))
            src.close()
            dst.close()


if __name__ == "__main__":
    unittest.main()
