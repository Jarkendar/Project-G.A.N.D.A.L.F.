#!/usr/bin/env python3
# Tests of the lab results store on synthetic data, in a throwaway brain/ made
# inside this folder.
#
#   python3 .claude/scripts/ioreth/test_labs.py

import sqlite3
import tempfile
import unittest
from pathlib import Path

import labs

HERE = Path(__file__).resolve().parent


def report(**changes):
    base = {
        "exam_date": "2026-03-02",
        "provider": "Diagnostyka",
        "identifiers": [{"label": "Nr zlecenia", "value": "TEST-001"}],
        "results": [
            {"material": "Krew", "param": "Glukoza", "name": "Glukoza", "value": "92", "unit": "mg/dl", "ref": "70 - 99"},
            {"material": "Krew", "param": "crp", "name": "CRP", "value": "<0,5", "unit": "mg/l", "ref": "< 5,0"},
        ],
        "attachments": ["/tmp/somewhere/1.png"],
    }
    base.update(changes)
    return base


class Parsing(unittest.TestCase):
    def test_values(self):
        self.assertEqual(labs.parse_value("4,50"), (4.5, None))
        self.assertEqual(labs.parse_value("< 0,5"), (0.5, "<"))
        self.assertEqual(labs.parse_value("≥60"), (60.0, ">="))
        self.assertEqual(labs.parse_value("ujemny"), (None, None))

    def test_status(self):
        for value, ref, expected in (
            ("92", "70 - 99", "within"),
            ("99", "70–99", "within"),
            ("100", "70 - 99", "above"),
            ("69,9", "70 - 99", "below"),
            ("-1", "-2 - 2", "within"),
            ("5,0", "< 5,0", "above"),
            ("5,0", "<= 5,0", "within"),
            ("<0,5", "< 5,0", "within"),
            ("<10", "< 5,0", "unknown"),
            (">90", "> 60", "within"),
            (">1000", "10 - 500", "above"),
            ("<2", "5 - 10", "below"),
            ("120", "optymalny < 100; graniczny 100 - 129", "unknown"),
            ("ujemny", "ujemny", "unknown"),
            ("5", None, "unknown"),
        ):
            self.assertEqual(labs.status(*labs.parse_value(value), ref), expected, f"{value} vs {ref}")


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=HERE, prefix="tmp-brain-")
        self.brain = Path(self.tmp.name)
        (self.brain / "db").mkdir()
        (self.brain / "core/health").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, data):
        return labs.save(self.brain, data, labs.digest(labs.normalise(data)))

    def files(self):
        return sorted(p.name for p in (self.brain / labs.REPORTS_DIR).glob("*.md"))

    def count(self, table):
        con = sqlite3.connect(self.brain / "db/labs.db")
        try:
            return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def test_preview_writes_nothing_and_matches_the_file(self):
        shown = labs.preview(self.brain, report())
        self.assertFalse((self.brain / "db/labs.db").exists())
        self.assertFalse((self.brain / labs.REPORTS_DIR).exists())
        self.assertIn(f"digest: {labs.digest(labs.normalise(report()))}", shown)
        self.save(report())
        written = (self.brain / labs.REPORTS_DIR / "2026-03-02_diagnostyka.md").read_text()
        body = shown.split("----- plik -----\n")[1]
        self.assertEqual(body.split("\n")[2:], written.split("\n")[2:])  # but for `date:`

    def test_file_and_rows(self):
        self.save(report())
        text = (self.brain / labs.REPORTS_DIR / "2026-03-02_diagnostyka.md").read_text()
        for expected in ("privacy: private", 'source: "Diagnostyka, Nr zlecenia: TEST-001', "tags: [health, lab-results]",
                         "| krew | CRP | <0,5 | mg/l | < 5,0 |  | crp |", "1.png", "Punkt pobrań: brak"):
            self.assertIn(expected, text)
        self.assertNotIn("/tmp/somewhere", text)
        self.assertEqual((self.count("reports"), self.count("results")), (1, 2))
        self.assertIn("core/health/labs/reports/2026-03-02_diagnostyka.md", labs.list_reports(self.brain))

    def test_changed_after_preview_is_refused(self):
        seen = labs.digest(labs.normalise(report()))
        other = report()
        other["results"][0]["value"] = "29"
        with self.assertRaises(labs.Refused):
            labs.save(self.brain, other, seen)
        self.assertFalse((self.brain / "db/labs.db").exists())

    def test_duplicate_refused_shared_number_only_warned(self):
        self.save(report())
        with self.assertRaises(labs.Refused):
            self.save(report())
        second = report(results=[{"material": "mocz", "param": "ph", "name": "pH", "value": "6,0"}])
        self.assertIn("TEST-001 jest już w badaniu 1", labs.preview(self.brain, second))
        self.save(second)
        self.assertEqual(self.files(), ["2026-03-02_diagnostyka.md", "2026-03-02_diagnostyka_2.md"])

    def test_missing_source(self):
        shown = labs.preview(self.brain, report(provider="", identifiers=[]))
        self.assertIn("brak placówki", shown)
        self.assertIn("brak numeru", shown)
        self.save(report(provider="", identifiers=[]))
        self.assertEqual(self.files(), ["2026-03-02_brak.md"])

    def test_correction_supersedes(self):
        self.save(report())
        original = (self.brain / labs.REPORTS_DIR / "2026-03-02_diagnostyka.md").read_text()
        fixed = report(supersedes=1)
        fixed["results"][0]["value"] = "29"
        self.save(fixed)
        self.assertEqual((self.count("reports"), self.count("results")), (2, 4))
        self.assertEqual((self.brain / labs.REPORTS_DIR / "2026-03-02_diagnostyka.md").read_text(), original)
        new = (self.brain / labs.REPORTS_DIR / "2026-03-02_diagnostyka_2.md").read_text()
        self.assertIn("supersedes: core/health/labs/reports/2026-03-02_diagnostyka.md", new)
        self.assertNotIn("| 92 |", labs.history(self.brain, "glukoza"))
        with self.assertRaises(labs.Refused):
            self.save(report(supersedes=1, results=fixed["results"][:1]))

    def test_descriptive(self):
        self.save(report(results=[], text="USG: opis testowy."))
        self.assertEqual((self.count("reports"), self.count("results")), (1, 0))
        self.assertIn("descriptive", labs.list_reports(self.brain))

    def test_trends(self):
        older = report(exam_date="2025-09-01", provider="Inne Lab", results=[
            {"material": "krew", "param": "glukoza", "name": "Glucose", "value": "80", "unit": "mg/dl", "ref": "70 - 105"},
            {"material": "krew", "param": "crp", "name": "CRP", "value": "1", "unit": "mg/dl"},
        ])
        self.save(report())
        self.save(older)  # saved later, dated earlier: the exam date orders
        latest = labs.compare(self.brain)
        self.assertIn("report 1 of 2026-03-02", latest)
        self.assertIn("+12 (+15%)", latest)
        self.assertIn("different unit (mg/dl)", latest)
        trend = labs.history(self.brain, "GLUKOZA")
        self.assertLess(trend.index("2025-09-01"), trend.index("2026-03-02"))
        self.assertIn("Inne Lab", trend)
        self.assertIn("glukoza", labs.history(self.brain))

    def test_refusals(self):
        for data in (
            report(exam_date="2026-3-2"),
            report(exam_date="2999-01-01"),
            report(results=[], text=""),
            report(surprise="x"),
            report(results=[{"material": "krew", "param": "x", "name": "X"}]),
            report(identifiers=[{"label": "PESEL", "value": "1"}]),
            report(text="Pacjent 44051401359"),
        ):
            with self.assertRaises(labs.Refused, msg=data):
                labs.preview(self.brain, data)

    def test_empty_reads(self):
        for answer in (labs.list_reports(self.brain), labs.history(self.brain), labs.compare(self.brain)):
            self.assertEqual(answer, "no results saved yet")
        self.assertFalse((self.brain / "db/labs.db").exists())

    def test_failed_write_leaves_nothing(self):
        original = labs.render
        labs.render = lambda *args: (_ for _ in ()).throw(OSError("disk full"))
        try:
            with self.assertRaises(OSError):
                self.save(report())
        finally:
            labs.render = original
        self.assertEqual((self.count("reports"), self.count("results")), (0, 0))
        self.assertEqual(self.files(), [])


if __name__ == "__main__":
    unittest.main()
