#!/usr/bin/env python3
# The dossier's hypotheses H1-H4 (8.9), the example configurations (8.4) and the
# sensitivity scenarios (8.10), printed from model.py. Results depend on the
# unverified parameters q, w and pi (V1-V7); read them as the model's, not the law's.
#
#   python3 .claude/scripts/oki/analysis.py

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model  # noqa: E402

EPS = 0.005
P = model.params()


def nets_for(K, r, T, p=P):
    return model.nets(model.pair_paths(K, r, p), T, p)


def breakeven(K, T, p=P):
    """The lowest r on a 0.05 pp grid from which OKI beats the plain account for good."""
    last_loss = None
    r = -0.04
    while r <= 0.12 + 1e-12:
        n = nets_for(K, round(r, 4), T, p)
        if n["B"] - n["A"] <= EPS:
            last_loss = round(r, 4)
        r += 0.0005
    return None if last_loss is None else round(last_loss + 0.0005, 4)


def h1():
    print("H1  OKI vs plain account above the limit: the rate from which OKI wins for good")
    print("    (theory without the limit: 0.85% / 19% = 4.5%; from year 2 the rate is 0.71%)")
    for K in (200_000, 500_000, 1_000_000):
        print("    K=%9d  " % K + "  ".join("T=%d: %s" % (T, _pct(breakeven(K, T))) for T in (5, 10, 20, 30, 50)))


def _pct(x):
    if x is None:
        return "always"
    return ">12%" if x > 0.12 else "%.2f%%" % (100 * x)


def h2():
    print("H2  K = 100k, q=100%: OKI pays no tax while the balance stays under the limit")
    print("    (the balance grows past L_n, which is indexed by 2.5% only)")
    flat = max(abs(nets_for(100_000, r, T)["B"] - nets_for(100_000, r, T)["A"])
               for r in model.R_AXIS if r <= 0 for T in model.T_AXIS)
    print("    r <= 0: largest |B-A| = %.4f zl" % flat)
    for r in (r for r in model.R_AXIS if r > 0):
        lost = [T for T in model.T_AXIS
                if (lambda n: n["B"] - n["A"] < -EPS)(nets_for(100_000, r, T))]
        print("    r=%2.0f%%: OKI behind the plain account at T = %s" % (100 * r, lost or "none"))


def h3():
    p = model.params(q=0.0)
    print("H3  q=0 (global ETF): OKI taxes the whole value")
    for r in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        wins = [(K, T) for K in model.K_AXIS for T in model.T_AXIS
                if (lambda n: n["B"] - n["A"] > EPS)(nets_for(K, r, T, p))]
        print("    r=%4.0f%%: OKI beats A in %3d of 100 (K,T) pairs" % (100 * r, len(wins)))


def h4():
    bad = []
    for K in model.K_AXIS:
        for r in model.R_AXIS:
            for T in (30, 35, 40, 45, 50):
                n = nets_for(K, r, T)
                if n["E"] < n["C"] - EPS:
                    bad.append((K, r, T, n["E"] - n["C"]))
    print("H4  E >= C for T >= 30: %d violations of 400" % len(bad))
    for K, r, T, d in bad[:8]:
        print("    K=%d r=%.0f%% T=%d  E-C = %.0f" % (K, 100 * r, T, d))
    if bad:
        print("    E-C from %.0f to %.0f; rates present: %s" % (
            min(b[3] for b in bad), max(b[3] for b in bad), sorted({b[1] for b in bad})))


def examples():
    print("Examples (net after liquidation, zl; real = net / (1+i)^T)")
    for K, r, T in ((100_000, 0.06, 20), (500_000, 0.04, 30), (1_000_000, 0.02, 50)):
        n = nets_for(K, r, T)
        gross = model.gross_no_tax(K, r, T, P)
        print("  K=%d r=%.0f%% T=%d  gross without tax %.0f; winner %s" % (K, 100 * r, T, gross, model.winner(n)))
        print("    " + "  ".join("%s %.0f (real %.0f)" % (v, n[v], n[v] / (1 + P["i"]) ** T) for v in model.VARIANTS))


SCEN = [
    ("base", {}),
    ("q=0 (global ETF)", {"q": 0.0}),
    ("NBPref=6%", {"NBPref": 0.06}),
    ("costs c=0.20%, k=0.10%", {"c": 0.002, "k_in": 0.001, "k_out": 0.001}),
    ("dividends s=100%", {"s": 1.0}),
    ("pi=0%", {"pi": 0.0}),
    ("pi=4%", {"pi": 0.04}),
    ("age 45", {"wiek0": 45}),
]


def scenarios():
    print("Scenarios: winners over the 800 configurations and the share where OKI (B) beats A")
    for name, over in SCEN:
        p = model.params(**over)
        rows = model.grid(p)["rows"]
        wins = {v: 0 for v in model.VARIANTS}
        b_over_a = 0
        for row in rows:
            wins[model.winner(row["net"])] += 1
            b_over_a += row["net"]["B"] - row["net"]["A"] > EPS
        print("  %-26s " % name + " ".join("%s=%3d" % (v, wins[v]) for v in model.VARIANTS)
              + "   B>A in %3d of 800" % b_over_a)


if __name__ == "__main__":
    for fn in (h1, h2, h3, h4, examples, scenarios):
        fn()
        print()
