#!/usr/bin/env python3
# Cases T1-T10 of the dossier (section 8.8) against model.py.
#
#   python3 .claude/scripts/oki/test_model.py

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model  # noqa: E402

P = model.params()
TOL = 0.01  # the dossier's hand values are rounded to a grosz


class HandComputed(unittest.TestCase):
    def test_t1_plain_account(self):
        path = model.path_a(100_000, 0.06, P)
        v = path["V"][10]
        self.assertAlmostEqual(v, 179_084.77, delta=TOL)
        self.assertAlmostEqual(v - 100_000, 79_084.77, delta=TOL)
        self.assertAlmostEqual(0.19 * (v - 100_000), 15_026.11, delta=TOL)
        self.assertAlmostEqual(model.net_a(path, 10, P), 164_058.66, delta=TOL)

    def test_t2_oki_year_one(self):
        path = model.path_oki(100_000, 0.06, P)
        self.assertAlmostEqual(100_000 * (1 + 0.5 * 0.06), 103_000, delta=TOL)
        self.assertAlmostEqual(path["Tax"][1], 25.50, delta=TOL)
        self.assertAlmostEqual(path["V"][1], 105_974.50, delta=TOL)

    def test_t3_oki_above_the_limit(self):
        path = model.path_oki(200_000, 0.0, P)
        self.assertAlmostEqual(path["Tax"][1], 850, delta=TOL)
        self.assertAlmostEqual(path["V"][1], 199_150, delta=TOL)

    def test_t4_plain_account_loss(self):
        path = model.path_a(100_000, -0.04, P)
        self.assertAlmostEqual(0.96 ** 5, 0.8153727, places=7)
        self.assertAlmostEqual(model.net_a(path, 5, P), 81_537.27, delta=TOL)


class Properties(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = model.grid(P)

    def test_t5_zero_rate_small_capital(self):
        for row in self.grid["rows"]:
            if row["r"] == 0.0 and row["K"] <= 100_000:
                for v in ("A", "B", "C"):
                    self.assertAlmostEqual(row["net"][v], row["K"], delta=TOL, msg=row)

    def test_t6_no_oki_tax(self):
        p = model.params(t1=0.0, NBPref=0.0, t_min=0.0)
        for row in model.grid(p)["rows"]:
            want = row["K"] * (1 + row["r"]) ** row["T"]
            self.assertAlmostEqual(row["net"]["B"], want, delta=TOL * max(1, want / 1e5), msg=row)

    def test_t7_no_belka(self):
        p = model.params(Belka=0.0)
        for row in model.grid(p)["rows"]:
            want = row["K"] * (1 + row["r"]) ** row["T"]
            self.assertAlmostEqual(row["net"]["A"], want, delta=TOL * max(1, want / 1e5), msg=row)

    def test_t8_ike_before_sixty(self):
        for row in self.grid["rows"]:
            if row["T"] <= 25:
                self.assertLessEqual(row["net"]["C"], row["net"]["A"] + TOL, msg=row)

    def test_t9_net_never_above_gross(self):
        for p in (P, model.params(c=0.002, k_in=0.001, k_out=0.001, F=50.0)):
            for row in model.grid(p)["rows"]:
                gross = model.gross_no_tax(row["K"], row["r"], row["T"], p)
                for v, net in row["net"].items():
                    self.assertLessEqual(net, gross + TOL, msg=(v, row))

    def test_t10_counts(self):
        self.assertEqual(len(self.grid["rows"]), 800)
        self.assertEqual(len(self.grid["pairs"]), 80)
        self.assertEqual(len({r["T"] for r in self.grid["rows"]}), 10)


class Rates(unittest.TestCase):
    def test_oki_rate_from_year_two(self):
        # 0.19 * 3.75% = 0.7125%, rounded down to 4 places = 0.71%
        self.assertEqual(model.oki_rate(1, P), 0.0085)
        self.assertEqual(model.oki_rate(2, P), 0.0071)

    def test_limit_indexed_from_year_four(self):
        self.assertEqual(model.oki_limit(3, P), 100_000)
        self.assertAlmostEqual(model.oki_limit(4, P), 102_500)

    def test_override(self):
        p = model.params(t_override={2: 0.01})
        self.assertEqual(model.oki_rate(2, p), 0.01)
        self.assertEqual(model.oki_rate(3, p), 0.0071)

    def test_ike_early_payout_is_taxed(self):
        # horizon 20 at age 30 ends at 50 < 60: tax on the IKE gain
        path = model.path_c(100_000, 0.06, P)
        early = model.net_c(path, 20, P)
        late = model.net_c(path, 30, model.params(wiek0=40))  # 70 >= 60
        self.assertGreater(late, 0)
        taxed = model.net_c(path, 20, model.params(wiek0=40))  # 60 >= 60
        self.assertGreater(taxed, early)


if __name__ == "__main__":
    unittest.main()
