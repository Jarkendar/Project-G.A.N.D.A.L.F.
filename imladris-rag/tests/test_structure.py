"""Hierarchy, line ranges, links and the schema-2 store. No model needed.
The store and context tests need a Qdrant server (docker-compose.yml) and
are skipped without one.

Run: python -m unittest discover imladris-rag/tests
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imladris import context, search, store  # noqa: E402
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

    def test_keyword_terms_meet_across_inflection(self):
        from imladris.qdrant_store import keyword_terms
        self.assertEqual(keyword_terms(["Polisie", "polisa", "Łódź", "kot"], 5), "polis polis lodz kot")
        self.assertEqual(keyword_terms(["Naleśniki"], 0), "nalesniki")

    def test_keywords_drop_stopwords(self):
        stop = frozenset({"jest"})
        self.assertEqual(search.keywords_from_query("kto jest uposażonym w polisie", stop),
                         ["kto", "uposażonym", "polisie"])
        self.assertIn("jest", search.keywords_from_query("kto jest"))  # the engine ships no stopwords

    def test_only_qdrant_locations_open(self):
        with self.assertRaises(ValueError):
            store.open_store("index/bilbo.db")

    def test_diversify_keeps_best_block_per_file(self):
        hits = [{"path": "a"}, {"path": "a"}, {"path": "b"}, {"path": "c"}]
        self.assertEqual([h["path"] for h in search.diversify(hits, 2)], ["a", "b"])


QDRANT_URL = "http://127.0.0.1:6333"


def unit(*v) -> bytes:
    """A normalized float32 vector, as the store expects it."""
    vec = np.array(v, dtype=np.float32)
    return (vec / np.linalg.norm(vec)).tobytes()


def sections_of(doc) -> list[dict]:
    return [{"heading": " > ".join(s.path) or "Doc", "section_no": s.number,
             "line_start": s.line_start, "line_end": s.line_end, "text": s.text} for s in doc.sections]


def blocks_of(doc, vectors, in_sections=True) -> list[dict]:
    """One block per chunk of `doc`, with `vectors[i]` (bytes) on the i-th."""
    return [{"heading": c.heading, "text": c.text, "section": c.section if in_sections else None,
             "line_start": c.line_start, "line_end": c.line_end, "token_count": count(c.text), "vector": v}
            for c, v in zip(doc.chunks, vectors)]


def one_block(vector: bytes, section=None) -> list[dict]:
    return [{"heading": "", "text": "x", "section": section, "line_start": 1, "line_end": 1,
             "token_count": 1, "vector": vector}]


def write(st, path, blocks, sections=(), links=(), title=None, privacy="public", **extra):
    """write_document with the bookkeeping fields every test leaves alone."""
    st.write_document(path, content_hash=f"h-{path}", mtime=0.0, indexed_at="now", title=title or path,
                      frontmatter={}, privacy=privacy, sections=list(sections), blocks=blocks,
                      links=list(links), **extra)


def finish(st, **meta):
    st.set_meta(**{"model_name": "m", "model_revision": "r", "embed_dim": "4",
                   "schema_version": store.SCHEMA_VERSION, **meta})
    st.commit()


class QdrantBackend:
    """Tests against a Qdrant server; skipped when none is running. Each test
    gets throwaway collections."""

    def setUp(self):
        try:
            from qdrant_client import QdrantClient
            self.client = QdrantClient(url=QDRANT_URL, timeout=2)
            self.client.get_collections()
        except Exception as err:
            self.skipTest(f"no Qdrant at {QDRANT_URL}: {err}")
        self.collections = []

    def tearDown(self):
        for name in self.collections:
            self.client.delete_collection(name)
        self.client.close()

    def location(self) -> str:
        self.collections.append(f"imladris_test_{uuid.uuid4().hex[:8]}")
        return f"{QDRANT_URL}/{self.collections[-1]}"


class ContextTest(QdrantBackend, unittest.TestCase):
    """build_context over a small store, with the query embedding faked."""

    def test_bundle_widens_hits_and_respects_budget(self):
        location = self.location()
        st = store.open_store(location)
        doc = parse_markdown(Path("d.md"), DOC, count)

        def along(axis, n):  # a.md along x, b.md along y; earlier blocks score higher
            v = [0.0] * 4
            v[axis], v[2] = 1.0 - 0.1 * n, 0.1 * n
            return unit(*v)

        for path, axis in (("a.md", 0), ("b.md", 1)):
            vectors = [along(axis, n) for n in range(len(doc.chunks))]
            write(st, path, blocks_of(doc, vectors), sections_of(doc), title="Doc", privacy="private")
        finish(st)
        st.close()

        idx = search.load_index(location)
        query = np.frombuffer(unit(0.9, 0.44, 0, 0), dtype=np.float32)
        with mock.patch.object(context, "embed_query", return_value=query):
            items = context.build_context(idx, "q", count, budget=1000, lead_files=2, doc_max=5)
            self.assertEqual([it.path for it in items[:2]], ["a.md", "b.md"])  # both lead files first
            self.assertTrue(all(it.kind == "section" for it in items))       # short sections widened
            self.assertEqual(len({(it.path, it.section_no) for it in items}), len(items))  # no repeats
            tight = context.build_context(idx, "q", count, budget=4, lead_files=2, doc_max=5)
            self.assertLessEqual(sum(it.tokens for it in tight), 4)

    def test_zmax_lets_a_document_vector_lead(self):
        def at(cos):  # a unit vector with this cosine to the query (x axis)
            return unit(cos, np.sqrt(1 - cos * cos), 0, 0)

        location = self.location()
        st = store.open_store(location)
        # c.md's block barely matches, but its summary names the category
        for path, block_cos, doc_cos in (("a.md", 0.9, 0.1), ("b.md", 0.5, 0.1), ("c.md", 0.1, 0.9)):
            write(st, path, one_block(at(block_cos), section=0),
                  sections=[{"heading": path, "section_no": "", "line_start": 1, "line_end": 1, "text": "x"}],
                  doc_text=f"{path} summary", doc_vector=at(doc_cos))
        finish(st)
        st.close()

        idx = search.load_index(location)
        self.assertEqual(idx.doc_paths, ["a.md", "b.md", "c.md"])
        with mock.patch.object(context, "embed_query", return_value=np.array([1, 0, 0, 0], dtype=np.float32)):
            lead = lambda rank: context.build_context(idx, "q", count, lead_files=1, links=False,
                                                      file_rank=rank)[0].path
            self.assertEqual(lead("blocks"), "a.md")
            self.assertEqual(lead("zmax"), "c.md")
            with self.assertRaises(ValueError):
                lead("max")


class StoreTest(QdrantBackend, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.doc = parse_markdown(Path("d.md"), DOC, count)
        self.st = store.open_store(self.location())

    def tearDown(self):
        self.st.close()
        super().tearDown()

    def write_doc(self):
        write(self.st, "d.md", blocks_of(self.doc, [unit(1, 1, 1, 1)] * len(self.doc.chunks)),
              sections_of(self.doc), title="Doc", privacy="private",
              links=[{"dst": "e.md", "raw": "e.md", "kind": "path", "line": 1}])
        finish(self.st)

    def test_document_tree_roundtrip(self):
        self.write_doc()
        title, privacy, sections, blocks = self.st.document("d.md")
        self.assertEqual((title, privacy, len(sections), len(blocks)), ("Doc", "private", 4, 4))
        # every block hangs under the section its chunk came from
        self.assertEqual([sections[b[1]][0] for b in blocks], ["", "1", "1.1", "2"])
        self.assertEqual(self.st.neighbours("d.md"), {"e.md"})
        self.assertEqual(self.st.neighbours("e.md"), {"d.md"})

        idx = search.load_index(self.st)
        self.assertEqual(len(idx.texts), 4)
        self.assertEqual(idx.section_nos, ["", "1", "1.1", "2"])
        # keyword search: only the block that has the word
        hits = search.fts_search(idx, "Deep things", top_k=3, stem=5)
        self.assertEqual([h["section_no"] for h in hits], ["1.1"])

    def test_delete_removes_blocks_and_links(self):
        self.write_doc()
        self.st.delete_document("d.md")
        self.st.commit()
        self.assertEqual(self.st.stored_hashes(), {})
        self.assertEqual(self.st.blocks(), [])
        self.assertEqual(self.st.neighbours("e.md"), set())

    def test_server_search_ranks_like_a_dot_product(self):
        vectors = [unit(1, i + 1, 0, 1) for i in range(len(self.doc.chunks))]  # all different: no ties
        write(self.st, "e.md", blocks_of(self.doc, vectors, in_sections=False))
        finish(self.st)
        rows = self.st.blocks()
        vectors = np.stack([np.frombuffer(r["vector"], dtype=np.float32) for r in rows])
        query = np.frombuffer(unit(2, 1, 0, 1), dtype=np.float32)
        local = [rows[i]["id"] for i in np.argsort(-(vectors @ query), kind="stable")[:3]]
        self.assertEqual([i for i, _ in self.st.nearest(query, 3, -1.0)], local)
        self.assertEqual(self.st.nearest(query, 3, 1.1), [])  # nothing clears the bar

    def test_an_index_built_otherwise_is_reported(self):
        write(self.st, "d.md", one_block(unit(1, 0, 0, 0)))
        finish(self.st, schema_version="1")
        with self.assertRaises(store.IndexMismatch):
            self.st.check_consistency("m", "r", "v2")
        self.st.set_meta(schema_version=store.SCHEMA_VERSION, chunker="v2")
        self.st.check_consistency("m", "r", "v2")          # same build: fine
        with self.assertRaises(store.IndexMismatch):
            self.st.check_consistency("other", "r", "v2")  # another model


if __name__ == "__main__":
    unittest.main()
