#!/usr/bin/env python3
# Reference model of the OKI account simulation (pure Python, no libraries).
#
# One yearly step, one asset with a constant rate r, a lump sum K at the start.
# Five ways to hold it: A a plain brokerage account, B OKI, C IKE + brokerage,
# D OKI + brokerage, E OKI + IKE + brokerage. The formulas are the ones of the
# project dossier, section 8; build_xlsx.py writes the same model as live
# Excel formulas and test_model.py checks this file against the dossier's
# hand-computed cases (T1-T4).
#
# Nothing here is a verified legal fact: q, w, pi and the rest of the V1-V7
# list are parameters in DEFAULTS, never constants in the code.

import math

N_MAX = 50  # years kept in every path (the longest horizon)

K_AXIS = [100_000 * i for i in range(1, 11)]
R_AXIS = [-0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]
T_AXIS = [5 * i for i in range(1, 11)]
VARIANTS = ["A", "B", "C", "D", "E"]

DEFAULTS = {
    "c": 0.0,            # fund cost (TER), a yearly rate
    "k_in": 0.0,         # entry cost
    "k_out": 0.0,        # exit cost
    "F": 0.0,            # yearly fee per account, charged while the balance > 0
    "Belka": 0.19,       # capital-gains tax
    "s": 0.0,            # share of the return paid out as dividend (0-1)
    "i": 0.025,          # inflation
    "t1": 0.0085,        # OKI rate in year 1 (2027)
    "NBPref": 0.0375,    # NBP reference rate, used from year 2
    "mult": 0.19,        # OKI rate = mult * NBPref (rounded down to 4 places)
    "t_min": 0.001,      # floor of the OKI rate
    "L0": 100_000.0,     # OKI exemption limit
    "pi": None,          # indexation of L0, from year 4; None = same as i
    "w": 0.5,            # weight of the year-average value: Vavg = V(1 + w r')
    "q": 1.0,            # share of qualifying assets (0 = a global ETF)
    "A_OKI": 100_000.0,  # amount put into OKI in variants D and E
    "Lim1": 28_260.0,    # IKE limit in year 1 (2027), the 2026 value
    "g": 0.05,           # yearly growth of the IKE limit
    "wiek0": 30,
    "wiek_IKE": 60,
    "warunek5": True,    # the five-year IKE condition
    "t_override": {},    # year -> OKI rate, replaces the formula
}


def params(**over):
    p = dict(DEFAULTS)
    p["t_override"] = dict(DEFAULTS["t_override"])
    p.update(over)
    return p


def pi_of(P):
    return P["i"] if P["pi"] is None else P["pi"]


def oki_rate(n, P):
    """t_n: the OKI rate in year n."""
    if n in P["t_override"] and P["t_override"][n] is not None:
        return P["t_override"][n]
    if n == 1:
        return P["t1"]
    return max(P["t_min"], math.floor(P["mult"] * P["NBPref"] * 1e4 + 1e-9) / 1e4)


def oki_limit(n, P):
    """L_n: the OKI exemption limit in year n."""
    return P["L0"] * (1 + pi_of(P)) ** max(0, n - 3)


def ike_limit(n, P):
    """Lim_n: the IKE contribution limit in year n."""
    return P["Lim1"] * (1 + P["g"]) ** (n - 1)


# ---- paths: state at the end of year n, n = 0..N_MAX -------------------------

def path_a(cap, r, P, n_max=N_MAX):
    rp = r - P["c"]
    V = [cap * (1 - P["k_in"])]
    B = [cap]
    for _ in range(n_max):
        v, b = V[-1], B[-1]
        d = P["s"] * rp * v if rp > 0 else 0.0
        V.append(max(0.0, v * (1 + rp) - P["Belka"] * d - (P["F"] if v > 0 else 0.0)))
        B.append(b + d - P["Belka"] * d)
    return {"V": V, "B": B}


def path_oki(cap, r, P, n_max=N_MAX):
    rp = r - P["c"]
    V = [cap * (1 - P["k_in"])]
    tax = [0.0]  # tax[n] is the tax of year n; tax[0] is a placeholder
    for n in range(1, n_max + 1):
        v = V[-1]
        vavg = v * (1 + P["w"] * rp)
        base = (1 - P["q"]) * vavg + max(0.0, P["q"] * vavg - oki_limit(n, P))
        t = oki_rate(n, P) * max(0.0, base)
        tax.append(t)
        V.append(max(0.0, v * (1 + rp) - t - (P["F"] if v > 0 else 0.0)))
    return {"V": V, "Tax": tax}


def path_c(cap, r, P, n_max=N_MAX):
    rp = r - P["c"]
    VB = [cap * (1 - P["k_in"])]
    BB = [cap]
    VI = [0.0]
    CI = [0.0]
    cn = [0.0]   # contribution of year n (sold from the brokerage account)
    wpl = [0.0]  # what reaches IKE: the contribution less the tax on the sale
    for n in range(1, n_max + 1):
        vb, bb, vi, ci = VB[-1], BB[-1], VI[-1], CI[-1]
        c_n = min(ike_limit(n, P), vb)
        f = c_n / vb if vb > 0 else 0.0
        w_n = c_n - P["Belka"] * f * max(0.0, vb - bb)
        vbr = vb - c_n
        bbr = bb * (1 - f)
        VI.append((vi + w_n) * (1 + rp) - (P["F"] if vi + w_n > 0 else 0.0))
        CI.append(ci + w_n)
        d = P["s"] * rp * vbr if rp > 0 else 0.0
        VB.append(max(0.0, vbr * (1 + rp) - P["Belka"] * d - (P["F"] if vbr > 0 else 0.0)))
        BB.append(bbr + d - P["Belka"] * d)
        cn.append(c_n)
        wpl.append(w_n)
    return {"VB": VB, "BB": BB, "VI": VI, "CI": CI, "cn": cn, "wpl": wpl}


# ---- liquidation at horizon T ------------------------------------------------

def net_a(path, T, P):
    vs = path["V"][T] * (1 - P["k_out"])
    return vs - P["Belka"] * max(0.0, vs - path["B"][T])


def net_oki(path, T, P):
    return path["V"][T] * (1 - P["k_out"])


def ike_paid_out_tax_free(T, P):
    return P["wiek0"] + T >= P["wiek_IKE"] and bool(P["warunek5"])


def net_c(path, T, P):
    vs_i = path["VI"][T] * (1 - P["k_out"])
    if ike_paid_out_tax_free(T, P):
        net_i = vs_i
    else:
        net_i = vs_i - P["Belka"] * max(0.0, vs_i - path["CI"][T])
    vs_b = path["VB"][T] * (1 - P["k_out"])
    net_b = vs_b - P["Belka"] * max(0.0, vs_b - path["BB"][T])
    return net_i + net_b


def oki_amount(K, P):
    return min(K, P["A_OKI"])


def pair_paths(K, r, P):
    """The paths of all five variants for one (capital, rate) pair."""
    a = oki_amount(K, P)
    return {
        "A": path_a(K, r, P),
        "B": path_oki(K, r, P),
        "C": path_c(K, r, P),
        "D_oki": path_oki(a, r, P),
        "D_rest": path_a(K - a, r, P),
        "E_oki": path_oki(a, r, P),
        "E_rest": path_c(K - a, r, P),
    }


def nets(paths, T, P):
    return {
        "A": net_a(paths["A"], T, P),
        "B": net_oki(paths["B"], T, P),
        "C": net_c(paths["C"], T, P),
        "D": net_oki(paths["D_oki"], T, P) + net_a(paths["D_rest"], T, P),
        "E": net_oki(paths["E_oki"], T, P) + net_c(paths["E_rest"], T, P),
    }


def gross_no_tax(K, r, T, P):
    return K * (1 - P["k_in"]) * (1 + r - P["c"]) ** T


def winner(n):
    """The variant with the highest net; ties (within half a grosz) go to the first."""
    top = max(n.values())
    return next(v for v in VARIANTS if n[v] >= top - 0.005)


def grid(P, k_axis=K_AXIS, r_axis=R_AXIS, t_axis=T_AXIS):
    """Every (K, r, T) configuration: {'pairs': [...], 'rows': [...]}.

    Pairs are K-major (the index runs over r inside K); rows are pair-major,
    with T innermost - the order the workbook uses.
    """
    pairs = []
    rows = []
    for K in k_axis:
        for r in r_axis:
            paths = pair_paths(K, r, P)
            pairs.append({"K": K, "r": r, "paths": paths})
            for T in t_axis:
                n = nets(paths, T, P)
                rows.append({"K": K, "r": r, "T": T, "pair": len(pairs), "net": n})
    return {"pairs": pairs, "rows": rows}


if __name__ == "__main__":
    g = grid(params())
    print(len(g["pairs"]), "pairs,", len(g["rows"]), "rows")
