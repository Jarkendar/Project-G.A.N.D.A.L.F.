#!/usr/bin/env python3
# Writes the OKI account simulation as an Excel workbook with live formulas.
#
#   python3 .claude/scripts/oki/build_xlsx.py [output.xlsx]
#
# Default output: output/oki-symulacje.xlsx in the repo root (gitignored).
# Needs xlsxwriter (.claude/scripts/oki/requirements.txt).
#
# Every formula is written together with the value model.py computed for it,
# so the file shows correct numbers before Excel recalculates anything. The
# values come from Python, not from the formulas: after opening the file in
# Excel (it recalculates on load) the sheet Kontrola_Python shows how far the
# formulas are from the Python values - that is the check of the formulas.
#
# Sheets: Parametry, Siatka, Lata, Silnik_A..E, Wyniki, Podsumowanie, Testy,
# Kontrola_Python. Formulas are in English syntax; parameters are named
# cells (par_*) that can be changed.

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import model  # noqa: E402

try:
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name as col_name
except ImportError:  # pragma: no cover
    sys.exit("xlsxwriter is not installed: pip install -r .claude/scripts/oki/requirements.txt")

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_OUT = os.path.join(REPO, "output", "oki-symulacje.xlsx")

NK, NR, NT = len(model.K_AXIS), len(model.R_AXIS), len(model.T_AXIS)
NP = NK * NR          # 80 pairs
NROWS = NP * NT       # 800 rows
NY = model.N_MAX + 1  # columns per block, n = 0..50
FIRST = 3             # first Excel row of data in the engine sheets and Siatka
BELKA_NOTE = "TAK/NIE: warunek 5 lat IKE"

# (key, label, number format, note)
PARAM_ROWS = [
    ("c", "c - TER (koszt funduszu, rocznie)", "pct2", ""),
    ("k_in", "k_in - koszt wejścia", "pct2", ""),
    ("k_out", "k_out - koszt wyjścia", "pct2", ""),
    ("F", "F - opłata roczna za konto (zł)", "money", "pobierana tylko gdy saldo > 0"),
    ("Belka", "Belka - podatek od zysków", "pct2", ""),
    ("s", "s - udział zwrotu wypłacany jako dywidenda", "pct2", "0 = fundusz akumulujący"),
    ("i", "i - inflacja", "pct2", ""),
    ("t1", "t1 - stawka OKI w roku 1 (2027)", "pct4", ""),
    ("NBPref", "NBPref - stopa referencyjna NBP od roku 2", "pct4", ""),
    ("mult", "mult - mnożnik stawki OKI", "pct2", "stawka od roku 2 = MAX(t_min; ROUNDDOWN(mult*NBPref; 4))"),
    ("t_min", "t_min - dolna granica stawki OKI", "pct4", ""),
    ("L0", "L0 - limit zwolnienia OKI (zł)", "money", ""),
    ("pi", "π - indeksacja L0, od roku 4", "pct2", "V6 niezweryfikowane; domyślnie = inflacja (formuła =par_i)"),
    ("w", "w - waga średniej wartości w roku", "num2", "V3 niezweryfikowane: Vavg = V(1 + w*r')"),
    ("q", "q - udział aktywów kwalifikowanych", "pct2", "V1/V2 niezweryfikowane; 0% = globalny ETF"),
    ("A_OKI", "A_OKI - kwota na OKI w wariantach D i E (zł)", "money", "V4"),
    ("Lim1", "Lim1 - limit IKE w roku 1 (2027) (zł)", "money", "V5: to wartość 2026"),
    ("g", "g - wzrost limitu IKE rocznie", "pct2", "V5"),
    ("wiek0", "wiek0 - wiek na starcie", "int", "założenie właściciela"),
    ("wiek_IKE", "wiek_IKE - wiek wypłaty IKE bez podatku", "int", ""),
    ("warunek5", "warunek5 - warunek 5 lat IKE", "text", BELKA_NOTE),
]

SCENARIOS = [
    ("Bazowy", "domyślne"),
    ("Globalny ETF", "q = 0%"),
    ("Wzrost stopy NBP", "NBPref = 6%"),
    ("Koszty realistyczne", "c = 0,20%; k_in = k_out = 0,10%"),
    ("Dywidendowe", "s = 100%"),
    ("Waloryzacja limitu", "π = 0% oraz π = 4%"),
    ("Wcześniejsza wypłata IKE", "wiek0 = 45"),
]


def W(ws, r, c, formula, value, fmt=None):
    """A formula cell with the value Python computed for it."""
    ws.write_formula(r, c, formula, fmt, value)


def build(path=DEFAULT_OUT, P=None):
    P = P or model.params()
    G = model.grid(P)
    pairs, rows = G["pairs"], G["rows"]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb = xlsxwriter.Workbook(path, {"use_future_functions": True})

    f = {
        "h": wb.add_format({"bold": True, "bg_color": "#DDEBF7", "border": 1, "text_wrap": True, "valign": "top"}),
        "title": wb.add_format({"bold": True, "font_size": 13}),
        "in": wb.add_format({"bg_color": "#FFF2CC", "border": 1}),
        "money": wb.add_format({"num_format": "#,##0.00"}),
        "money_in": wb.add_format({"num_format": "#,##0.00", "bg_color": "#FFF2CC", "border": 1}),
        "pct2": wb.add_format({"num_format": "0.00%"}),
        "pct2_in": wb.add_format({"num_format": "0.00%", "bg_color": "#FFF2CC", "border": 1}),
        "pct4_in": wb.add_format({"num_format": "0.0000%", "bg_color": "#FFF2CC", "border": 1}),
        "pct4": wb.add_format({"num_format": "0.0000%"}),
        "num2_in": wb.add_format({"num_format": "0.00", "bg_color": "#FFF2CC", "border": 1}),
        "int_in": wb.add_format({"num_format": "0", "bg_color": "#FFF2CC", "border": 1}),
        "text_in": wb.add_format({"bg_color": "#FFF2CC", "border": 1}),
        "int": wb.add_format({"num_format": "0"}),
        "wrap": wb.add_format({"text_wrap": True, "valign": "top"}),
        "good": wb.add_format({"bg_color": "#C6EFCE"}),
        "bad": wb.add_format({"bg_color": "#FFC7CE"}),
    }

    # ---- Parametry --------------------------------------------------------
    ws = wb.add_worksheet("Parametry")
    ws.set_column(0, 0, 52)
    ws.set_column(1, 1, 16)
    ws.set_column(2, 2, 14)
    ws.set_column(3, 3, 70)
    ws.write(0, 0, "Parametry modelu - żółte komórki można zmieniać", f["title"])
    for c, t in enumerate(["Parametr", "Wartość", "Nazwa komórki", "Uwagi"]):
        ws.write(1, c, t, f["h"])
    for k, (key, label, kind, note) in enumerate(PARAM_ROWS):
        r = 2 + k
        ws.write(r, 0, label)
        ws.write(r, 2, "par_" + key)
        ws.write(r, 3, note)
        fmt = f[kind + "_in"]
        if key == "pi":
            if P["pi"] is None:
                W(ws, r, 1, "=par_i", model.pi_of(P), fmt)
            else:
                ws.write_number(r, 1, P["pi"], fmt)
        elif key == "warunek5":
            ws.write(r, 1, "TAK" if P["warunek5"] else "NIE", fmt)
        else:
            ws.write_number(r, 1, P[key], fmt)
        wb.define_name("par_" + key, "=Parametry!$B$%d" % (r + 1))
    r0 = 2 + len(PARAM_ROWS) + 1
    ws.write(r0, 0, "Scenariusze wrażliwości (zmień komórki ręcznie)", f["title"])
    for k, (name, what) in enumerate(SCENARIOS):
        ws.write(r0 + 1 + k, 0, name)
        ws.write(r0 + 1 + k, 3, what)
    ws.write(r0 + 2 + len(SCENARIOS), 0,
             "Rok 1 = 2027. Stawka OKI w poszczególnych latach: arkusz Lata, kolumna E (nadpisanie).", f["wrap"])
    ws.write(r0 + 3 + len(SCENARIOS), 0,
             "Punkty V1-V7 z dossier są niezweryfikowane (q, w, π, limity, próg 70%) - dlatego są parametrami.", f["wrap"])

    # ---- Siatka -----------------------------------------------------------
    ws = wb.add_worksheet("Siatka")
    ws.set_column(0, 8, 14)
    ws.write(0, 0, "Osie siatki (żółte - można zmieniać) i lista par (K, r)", f["title"])
    for c, t in enumerate(["K (kapitał)", "r (stopa)", "T (horyzont)"]):
        ws.write(1, c, t, f["h"])
    for k, v in enumerate(model.K_AXIS):
        ws.write_number(FIRST - 1 + k, 0, v, f["money_in"])
    for k, v in enumerate(model.R_AXIS):
        ws.write_number(FIRST - 1 + k, 1, v, f["pct2_in"])
    for k, v in enumerate(model.T_AXIS):
        ws.write_number(FIRST - 1 + k, 2, v, f["int_in"])
    for c, t in enumerate(["para", "K", "r"]):
        ws.write(1, 4 + c, t, f["h"])
    for p, pr in enumerate(pairs):
        ik, ir = divmod(p, NR)
        ws.write_number(FIRST - 1 + p, 4, p + 1, f["int"])
        W(ws, FIRST - 1 + p, 5, "=$A$%d" % (FIRST + ik), pr["K"], f["money"])
        W(ws, FIRST - 1 + p, 6, "=$B$%d" % (FIRST + ir), pr["r"], f["pct2"])

    # ---- Lata -------------------------------------------------------------
    ws = wb.add_worksheet("Lata")
    ws.set_column(0, 4, 18)
    ws.write(0, 0, "Wielkości zależne od roku (rok 1 = 2027)", f["title"])
    for c, t in enumerate(["rok n", "t_n (stawka OKI)", "L_n (limit OKI)", "Lim_n (limit IKE)",
                           "nadpisanie t_n (puste = wzór)"]):
        ws.write(1, c, t, f["h"])
    for n in range(1, model.N_MAX + 1):
        r = 1 + n
        e = "E%d" % (r + 1)
        ws.write_number(r, 0, n, f["int"])
        W(ws, r, 1, '=IF(%s<>"",%s,IF(A%d=1,par_t1,MAX(par_t_min,ROUNDDOWN(par_mult*par_NBPref,4))))'
          % (e, e, r + 1), model.oki_rate(n, P), f["pct4"])
        W(ws, r, 2, "=par_L0*(1+par_pi)^MAX(0,A%d-3)" % (r + 1), model.oki_limit(n, P), f["money"])
        W(ws, r, 3, "=par_Lim1*(1+par_g)^(A%d-1)" % (r + 1), model.ike_limit(n, P), f["money"])
        if n in P["t_override"]:
            ws.write_number(r, 4, P["t_override"][n], f["pct4_in"])
        else:
            ws.write_blank(r, 4, None, f["in"])

    # ---- Silnik_A..E ------------------------------------------------------
    kinds = {"A": ["V", "B"], "OKI": ["V", "Tax"], "C": ["VB", "BB", "VI", "CI", "cn", "wpl"]}
    # sheet: (capital columns, components (kind, capital column, path key))
    specs = {
        "A": ([("kapitał", "=B{R}", lambda K: K)], [("A", 4, "A")]),
        "B": ([("kapitał", "=B{R}", lambda K: K)], [("OKI", 4, "B")]),
        "C": ([("kapitał", "=B{R}", lambda K: K)], [("C", 4, "C")]),
        "D": ([("kapitał w OKI (a)", "=MIN(B{R},par_A_OKI)", lambda K: model.oki_amount(K, P)),
               ("reszta K-a", "=B{R}-E{R}", lambda K: K - model.oki_amount(K, P))],
              [("OKI", 4, "D_oki"), ("A", 5, "D_rest")]),
        "E": ([("kapitał w OKI (a)", "=MIN(B{R},par_A_OKI)", lambda K: model.oki_amount(K, P)),
               ("reszta K-a", "=B{R}-E{R}", lambda K: K - model.oki_amount(K, P))],
              [("OKI", 4, "E_oki"), ("C", 5, "E_rest")]),
    }
    blocks = {}  # (sheet, component index) -> {block name: start column}
    for sheet, (caps, comps) in specs.items():
        ws = wb.add_worksheet("Silnik_" + sheet)
        ws.set_column(0, 0, 6)
        ws.set_column(1, 3 + len(caps), 13)
        ws.freeze_panes(2, 4 + len(caps))
        ws.write(0, 0, "Silnik %s: stan na końcu roku n (n = 0 to start); jeden wiersz na parę (K, r)" % sheet, f["title"])
        for c, t in enumerate(["para", "K", "r", "r' = r - c"] + [c_[0] for c_ in caps]):
            ws.write(1, c, t, f["h"])
        col = 4 + len(caps)
        for ci, (kind, _capcol, _key) in enumerate(comps):
            blocks[(sheet, ci)] = {}
            for name in kinds[kind]:
                blocks[(sheet, ci)][name] = col
                ws.write(0, col, "%s (%s)" % (name, kind) if len(comps) > 1 else name, f["h"])
                for n in range(NY):
                    ws.write_number(1, col + n, n, f["int"])
                col += NY
        for p, pr in enumerate(pairs):
            R = FIRST + p  # Excel row
            r0 = R - 1
            W(ws, r0, 0, "=Siatka!E%d" % R, p + 1, f["int"])
            W(ws, r0, 1, "=Siatka!F%d" % R, pr["K"], f["money"])
            W(ws, r0, 2, "=Siatka!G%d" % R, pr["r"], f["pct2"])
            W(ws, r0, 3, "=C%d-par_c" % R, pr["r"] - P["c"], f["pct4"])
            for k, (_h, tmpl, fn) in enumerate(caps):
                W(ws, r0, 4 + k, tmpl.format(R=R), fn(pr["K"]), f["money"])
            for ci, (kind, capcol, key) in enumerate(comps):
                _write_component(ws, wb, f, r0, R, kind, col_name(capcol), blocks[(sheet, ci)],
                                 pr["paths"][key], P)

    # ---- Wyniki -----------------------------------------------------------
    ws = wb.add_worksheet("Wyniki")
    ws.freeze_panes(1, 4)
    ws.set_column(0, 3, 12)
    ws.set_column(4, 26, 15)
    ws.set_column(27, 41, 15)
    helpers = [  # name, sheet, component, block
        ("A_V", "A", 0, "V"), ("A_B", "A", 0, "B"),
        ("B_V", "B", 0, "V"),
        ("C_VB", "C", 0, "VB"), ("C_BB", "C", 0, "BB"), ("C_VI", "C", 0, "VI"), ("C_CI", "C", 0, "CI"),
        ("D_O", "D", 0, "V"), ("D_V", "D", 1, "V"), ("D_B", "D", 1, "B"),
        ("E_O", "E", 0, "V"), ("E_VB", "E", 1, "VB"), ("E_BB", "E", 1, "BB"),
        ("E_VI", "E", 1, "VI"), ("E_CI", "E", 1, "CI"),
    ]
    pathkey = {"A": "A", "B": "B", "C": "C", "D0": "D_oki", "D1": "D_rest", "E0": "E_oki", "E1": "E_rest"}
    HC0 = 27
    hcol = {name: HC0 + k for k, (name, *_x) in enumerate(helpers)}
    head = (["K", "r", "T", "para"] + ["Net_" + v for v in model.VARIANTS]
            + ["Brutto_bez_podatku", "Delta_B_A", "Zwycięzca"]
            + ["Obciążenie_" + v for v in model.VARIANTS]
            + ["Net_real_" + v for v in model.VARIANTS]
            + ["CAGR_netto_" + v for v in model.VARIANTS]
            + ["h_" + h[0] for h in helpers])
    for c, t in enumerate(head):
        ws.write(0, c, t, f["h"])
    last = NROWS + 1

    def ref(name, R):
        return "$%s%d" % (col_name(hcol[name]), R)

    def net_a(v, b):
        return "(%s*(1-par_k_out)-par_Belka*MAX(0,%s*(1-par_k_out)-%s))" % (v, v, b)

    def net_c(vb, bb, vi, ci, tc):
        vsi = "%s*(1-par_k_out)" % vi
        return net_a(vb, bb) + '+IF(AND(par_wiek0+%s>=par_wiek_IKE,par_warunek5="TAK"),%s,%s-par_Belka*MAX(0,%s-%s))' % (
            tc, vsi, vsi, vsi, ci)

    for idx, row in enumerate(rows):
        R = idx + 2
        r0 = R - 1
        p, it = divmod(idx, NT)
        ik, ir = divmod(p, NR)
        pr = pairs[p]
        K, r, T = row["K"], row["r"], row["T"]
        W(ws, r0, 0, "=Siatka!$F$%d" % (FIRST + p), K, f["money"])
        W(ws, r0, 1, "=Siatka!$G$%d" % (FIRST + p), r, f["pct2"])
        W(ws, r0, 2, "=Siatka!$C$%d" % (FIRST + it), T, f["int"])
        ws.write_number(r0, 3, p + 1, f["int"])
        # helper columns: the state of a path at the horizon
        hv = {}
        for name, sheet, ci, blk in helpers:
            start = blocks[(sheet, ci)][blk]
            key = pathkey[sheet] if sheet in "ABC" else pathkey[sheet + str(ci)]
            rng = "Silnik_%s!$%s$%d:$%s$%d" % (sheet, col_name(start), FIRST, col_name(start + NY - 1), FIRST + NP - 1)
            val = pr["paths"][key][blk][T]
            hv[name] = val
            W(ws, r0, hcol[name], "=INDEX(%s,$D%d,$C%d+1)" % (rng, R, R), val, f["money"])
        Tc = "$C%d" % R
        nf = [
            net_a(ref("A_V", R), ref("A_B", R)),
            "%s*(1-par_k_out)" % ref("B_V", R),
            net_c(ref("C_VB", R), ref("C_BB", R), ref("C_VI", R), ref("C_CI", R), Tc),
            "%s*(1-par_k_out)+%s" % (ref("D_O", R), net_a(ref("D_V", R), ref("D_B", R))),
            "%s*(1-par_k_out)+%s" % (ref("E_O", R), net_c(ref("E_VB", R), ref("E_BB", R), ref("E_VI", R),
                                                           ref("E_CI", R), Tc)),
        ]
        net = row["net"]
        gross = model.gross_no_tax(K, r, T, P)
        for k, v in enumerate(model.VARIANTS):
            W(ws, r0, 4 + k, "=" + nf[k], net[v], f["money"])
        W(ws, r0, 9, "=$A%d*(1-par_k_in)*(1+$B%d-par_c)^$C%d" % (R, R, R), gross, f["money"])
        W(ws, r0, 10, "=F%d-E%d" % (R, R), net["B"] - net["A"], f["money"])
        W(ws, r0, 11, '=INDEX({"A","B","C","D","E"},MATCH(TRUE,INDEX(E%d:I%d>=MAX(E%d:I%d)-0.005,0),0))'
          % (R, R, R, R), model.winner(net), None)
        for k, v in enumerate(model.VARIANTS):
            nc = "%s%d" % (col_name(4 + k), R)
            W(ws, r0, 12 + k, "=$J%d-%s" % (R, nc), gross - net[v], f["money"])
            W(ws, r0, 17 + k, "=%s/(1+par_i)^$C%d" % (nc, R), net[v] / (1 + P["i"]) ** T, f["money"])
            cagr = (net[v] / K) ** (1 / T) - 1 if net[v] > 0 else ""
            W(ws, r0, 22 + k, '=IF(%s>0,(%s/$A%d)^(1/$C%d)-1,"")' % (nc, nc, R, R), cagr, f["pct2"])

    def wrow(p, it):  # Excel row in Wyniki of pair p (0-based), horizon index it
        return 2 + p * NT + it

    # ---- Podsumowanie -----------------------------------------------------
    ws = wb.add_worksheet("Podsumowanie")
    ws.set_column(0, 9, 13)
    ws.set_column(10, 19, 9)
    ws.write(0, 0, "Dla każdego horyzontu T: różnica Net_B - Net_A (po lewej) i zwycięzca (po prawej); wiersze K, kolumny r",
             f["title"])
    BLOCK = 13
    delta_ranges, win_ranges = [], []
    for it, T in enumerate(model.T_AXIS):
        top = 2 + it * BLOCK
        W(ws, top, 0, '="T = "&Siatka!$C$%d&" lat"' % (FIRST + it), "T = %d lat" % T, f["title"])
        ws.write(top + 1, 0, "K \\ r", f["h"])
        ws.write(top + 1, 10, "K \\ r", f["h"])
        for ir, rr in enumerate(model.R_AXIS):
            W(ws, top + 1, 1 + ir, "=Siatka!$B$%d" % (FIRST + ir), rr, f["h"])
            W(ws, top + 1, 11 + ir, "=Siatka!$B$%d" % (FIRST + ir), rr, f["h"])
        for ik, K in enumerate(model.K_AXIS):
            rr0 = top + 2 + ik
            W(ws, rr0, 0, "=Siatka!$A$%d" % (FIRST + ik), K, f["money"])
            W(ws, rr0, 10, "=Siatka!$A$%d" % (FIRST + ik), K, f["money"])
            for ir in range(NR):
                p = ik * NR + ir
                row = rows[p * NT + it]
                R = wrow(p, it)
                W(ws, rr0, 1 + ir, "=Wyniki!$K$%d" % R, row["net"]["B"] - row["net"]["A"], f["money"])
                W(ws, rr0, 11 + ir, "=Wyniki!$L$%d" % R, model.winner(row["net"]), None)
        delta_ranges.append((top + 2, 1, top + 11, NR))
        win_ranges.append((top + 2, 11, top + 11, 10 + NR))
    for rng in delta_ranges:
        ws.conditional_format(*rng, {"type": "cell", "criteria": ">", "value": 0.005, "format": f["good"]})
        ws.conditional_format(*rng, {"type": "cell", "criteria": "<", "value": -0.005, "format": f["bad"]})
    colors = {"A": "#F8CBAD", "B": "#C6E0B4", "C": "#BDD7EE", "D": "#FFE699", "E": "#D9C3E8"}
    for rng in win_ranges:
        for v, color in colors.items():
            ws.conditional_format(*rng, {"type": "cell", "criteria": "==", "value": '"%s"' % v,
                                         "format": wb.add_format({"bg_color": color})})
    base = 2 + NT * BLOCK + 1
    ws.write(base, 0, "Najkrótszy horyzont, od którego Net_B > Net_A (próg 0,005 zł; 'brak' = nigdy w siatce)", f["title"])
    for c, t in enumerate(["K", "r", "T_min"]):
        ws.write(base + 1, c, t, f["h"])
    for p, pr in enumerate(pairs):
        r0 = base + 2 + p
        ws.write_formula(r0, 0, "=Siatka!F%d" % (FIRST + p), f["money"], pr["K"])
        ws.write_formula(r0, 1, "=Siatka!G%d" % (FIRST + p), f["pct2"], pr["r"])
        win_T = [row["T"] for row in rows[p * NT:(p + 1) * NT] if row["net"]["B"] - row["net"]["A"] > 0.005]
        crit = 'Wyniki!$D$2:$D$%d,%d,Wyniki!$K$2:$K$%d,">0.005"' % (last, p + 1, last)
        W(ws, r0, 2, '=IF(COUNTIFS(%s)=0,"brak",MINIFS(Wyniki!$C$2:$C$%d,%s))' % (crit, last, crit),
          min(win_T) if win_T else "brak", f["int"])
    ws.write(base, 6, "Zwycięzcy: liczba konfiguracji (z 80) na horyzont", f["title"])
    ws.write(base + 1, 6, "T", f["h"])
    for k, v in enumerate(model.VARIANTS):
        ws.write(base + 1, 7 + k, v, f["h"])
    for it, T in enumerate(model.T_AXIS):
        r0 = base + 2 + it
        W(ws, r0, 6, "=Siatka!$C$%d" % (FIRST + it), T, f["int"])
        for k, v in enumerate(model.VARIANTS):
            cnt = sum(1 for p in range(NP) if model.winner(rows[p * NT + it]["net"]) == v)
            W(ws, r0, 7 + k, '=COUNTIFS(Wyniki!$C$2:$C$%d,$G%d,Wyniki!$L$2:$L$%d,"%s")' % (last, r0 + 1, last, v),
              cnt, f["int"])

    # ---- Testy ------------------------------------------------------------
    ws = wb.add_worksheet("Testy")
    ws.set_column(0, 0, 8)
    ws.set_column(1, 1, 70)
    ws.set_column(2, 5, 16)
    ws.write(0, 0, "Testy T1-T10 z dossier (8.8)", f["title"])
    defaults_ok = ("AND(par_c=0,par_k_in=0,par_k_out=0,par_F=0,par_Belka=0.19,par_s=0,par_t1=0.0085,"
                   "par_NBPref=0.0375,par_mult=0.19,par_t_min=0.001,par_L0=100000,par_w=0.5,par_q=1,"
                   "Siatka!$A$3=100000,Siatka!$A$4=200000,Siatka!$B$3=-0.04,Siatka!$B$5=0,Siatka!$B$8=0.06,"
                   "Siatka!$C$3=5,Siatka!$C$4=10)")
    is_default = (P["c"] == 0 and P["k_in"] == 0 and P["k_out"] == 0 and P["F"] == 0 and P["Belka"] == 0.19
                  and P["s"] == 0 and P["t1"] == 0.0085 and P["NBPref"] == 0.0375 and P["mult"] == 0.19
                  and P["t_min"] == 0.001 and P["L0"] == 100000 and P["w"] == 0.5 and P["q"] == 1)
    ws.write(1, 0, "Wartości oczekiwane z ręcznych obliczeń obowiązują dla parametrów domyślnych:", f["wrap"])
    W(ws, 1, 3, "=IF(%s,\"tak\",\"nie\")" % defaults_ok, "tak" if is_default else "nie", None)
    for c, t in enumerate(["ID", "Opis", "Obliczona", "Oczekiwana", "Tolerancja", "Wynik"]):
        ws.write(2, c, t, f["h"])

    def at(p, it):
        return rows[p * NT + it]

    p_1006 = 0 * NR + 5   # K=100k, r=6%
    p_2000 = 1 * NR + 2   # K=200k, r=0%
    p_1m4 = 0             # K=100k, r=-4%
    b_start = blocks[("B", 0)]
    ha = hcol["A_V"]
    tests = []  # (id, description, formula, value, expected, tol)
    tests.append(("T1", "A: K=100k, r=6%, T=10: V_T", "=Wyniki!$%s$%d" % (col_name(ha), wrow(p_1006, 1)),
                  pairs[p_1006]["paths"]["A"]["V"][10], 179084.77, 0.01))
    tests.append(("T1", "A: K=100k, r=6%, T=10: Net_A", "=Wyniki!$E$%d" % wrow(p_1006, 1),
                  at(p_1006, 1)["net"]["A"], 164058.66, 0.01))
    tests.append(("T2", "B: K=100k, r=6%: podatek roku 1",
                  "=Silnik_B!$%s$%d" % (col_name(b_start["Tax"] + 1), FIRST + p_1006),
                  pairs[p_1006]["paths"]["B"]["Tax"][1], 25.50, 0.01))
    tests.append(("T2", "B: K=100k, r=6%: V1", "=Silnik_B!$%s$%d" % (col_name(b_start["V"] + 1), FIRST + p_1006),
                  pairs[p_1006]["paths"]["B"]["V"][1], 105974.50, 0.01))
    tests.append(("T3", "B: K=200k, r=0%: podatek roku 1",
                  "=Silnik_B!$%s$%d" % (col_name(b_start["Tax"] + 1), FIRST + p_2000),
                  pairs[p_2000]["paths"]["B"]["Tax"][1], 850.0, 0.01))
    tests.append(("T3", "B: K=200k, r=0%: V1", "=Silnik_B!$%s$%d" % (col_name(b_start["V"] + 1), FIRST + p_2000),
                  pairs[p_2000]["paths"]["B"]["V"][1], 199150.0, 0.01))
    tests.append(("T4", "A: K=100k, r=-4%, T=5: Net_A", "=Wyniki!$E$%d" % wrow(p_1m4, 0),
                  at(p_1m4, 0)["net"]["A"], 81537.27, 0.01))
    r_end = last
    A = lambda c: "Wyniki!$%s$2:$%s$%d" % (c, c, r_end)  # noqa: E731
    rows_ = rows
    # T5: violations (count) must be 0
    t5 = sum(1 for r_ in rows_ if r_["r"] == 0 and r_["K"] <= P["L0"]
             for v in "ABC" if abs(r_["net"][v] - r_["K"]) > 0.01)
    tests.append(("T5", "r=0%, K <= L0: A, B, C = K (liczba odstępstw)",
                  "=SUMPRODUCT((%s=0)*(%s<=par_L0)*((ABS(%s-%s)>0.01)+(ABS(%s-%s)>0.01)+(ABS(%s-%s)>0.01)))"
                  % (A("B"), A("A"), A("E"), A("A"), A("F"), A("A"), A("G"), A("A")), t5, 0, 0))
    z6 = P["t1"] == 0 and P["NBPref"] == 0 and P["t_min"] == 0 and P["k_in"] == 0 and P["k_out"] == 0 and P["F"] == 0
    z7 = P["Belka"] == 0 and P["k_in"] == 0 and P["k_out"] == 0 and P["F"] == 0
    for tid, desc, cond, col, ok in (
        ("T6", "t1 = NBPref = t_min = 0 (koszty 0): Net_B = K(1+r')^T (liczba odstępstw; N/D gdy warunek nie zachodzi)",
         "AND(par_t1=0,par_NBPref=0,par_t_min=0,par_k_in=0,par_k_out=0,par_F=0)", "F", z6),
        ("T7", "Belka = 0 (koszty 0): Net_A = K(1+r')^T (liczba odstępstw; N/D gdy warunek nie zachodzi)",
         "AND(par_Belka=0,par_k_in=0,par_k_out=0,par_F=0)", "E", z7),
    ):
        col_idx = 5 if col == "F" else 4
        val = sum(1 for r_ in rows_ if abs(r_["net"]["B" if col == "F" else "A"]
                                           - model.gross_no_tax(r_["K"], r_["r"], r_["T"], P)) > 0.01) if ok else ""
        tests.append((tid, desc, '=IF(%s,SUMPRODUCT(--(ABS(%s-%s)>0.01)),"")' % (cond, A(col), A("J")), val, 0, 0))
    t8 = sum(1 for r_ in rows_ if P["wiek0"] + r_["T"] < P["wiek_IKE"] and r_["net"]["C"] > r_["net"]["A"] + 0.01)
    tests.append(("T8", "IKE wypłacane przed wiekiem wypłaty: Net_C <= Net_A (liczba odstępstw)",
                  "=SUMPRODUCT((par_wiek0+%s<par_wiek_IKE)*(%s>%s+0.01))" % (A("C"), A("G"), A("E")), t8, 0, 0))
    t9ok = P["c"] >= 0 and P["k_in"] >= 0 and P["k_out"] >= 0 and P["F"] >= 0
    t9 = sum(1 for r_ in rows_ for v in model.VARIANTS
             if r_["net"][v] > model.gross_no_tax(r_["K"], r_["r"], r_["T"], P) + 0.01) if t9ok else ""
    tests.append(("T9", "Net <= Brutto_bez_podatku dla wszystkich wariantów (liczba odstępstw; koszty >= 0)",
                  '=IF(AND(par_c>=0,par_k_in>=0,par_k_out>=0,par_F>=0),'
                  'SUMPRODUCT(--(Wyniki!$E$2:$I$%d>Wyniki!$J$2:$J$%d+0.01)),"")' % (r_end, r_end), t9, 0, 0))
    tests.append(("T10", "Liczba wierszy w Wyniki", "=COUNT(Wyniki!$A$2:$A$%d)" % r_end, len(rows_), 800, 0))
    tests.append(("T10", "Liczba par (K, r)", "=COUNT(Siatka!$E$3:$E$%d)" % (FIRST + NP - 1), len(pairs), 80, 0))
    tests.append(("T10", "Liczba horyzontów", "=COUNT(Siatka!$C$3:$C$%d)" % (FIRST + NT - 1), NT, 10, 0))
    needs_default = {"T1", "T2", "T3", "T4"}
    results = []
    for k, (tid, desc, formula, val, exp, tol) in enumerate(tests):
        r0 = 3 + k
        R = r0 + 1
        ws.write(r0, 0, tid)
        ws.write(r0, 1, desc, f["wrap"])
        W(ws, r0, 2, formula, val, f["money"])
        ws.write_number(r0, 3, exp, f["money"])
        ws.write_number(r0, 4, tol, f["money"])
        core = 'IF(C%d="","N/D",IF(ABS(C%d-D%d)<=E%d,"OK","BŁĄD"))' % (R, R, R, R)
        if tid in needs_default:
            formula_res = '=IF($D$2="tak",%s,"N/D")' % core
            res = ("N/D" if not is_default else ("OK" if abs(val - exp) <= tol else "BŁĄD"))
        else:
            formula_res = "=" + core
            res = "N/D" if val == "" else ("OK" if abs(val - exp) <= tol else "BŁĄD")
        W(ws, r0, 5, formula_res, res, None)
        results.append(res)
    end = 3 + len(tests)
    ws.write(end + 1, 1, "Podsumowanie", f["title"])
    W(ws, end + 1, 5, '=IF(COUNTIF($F$4:$F$%d,"BŁĄD")=0,"BRAK BŁĘDÓW","SĄ BŁĘDY")' % end,
      "BRAK BŁĘDÓW" if "BŁĄD" not in results else "SĄ BŁĘDY", None)
    ws.conditional_format(3, 5, end + 1, 5, {"type": "text", "criteria": "containing", "value": "BŁĄD",
                                              "format": f["bad"]})
    ws.conditional_format(3, 5, end + 1, 5, {"type": "cell", "criteria": "==", "value": '"OK"', "format": f["good"]})

    # ---- Kontrola_Python --------------------------------------------------
    ws = wb.add_worksheet("Kontrola_Python")
    ws.set_column(0, 12, 15)
    ws.write(0, 0, "Wartości Net policzone niezależnie w Pythonie (stałe, dla parametrów bazowych) i różnica "
             "względem formuł w arkuszu Wyniki. Po zmianie parametrów różnica rośnie - to oczekiwane.", f["wrap"])
    ws.write(1, 0, "Maks. różnica (zł):")
    W(ws, 1, 3, "=MAX(MAX(I4:M%d),-MIN(I4:M%d))" % (NROWS + 3, NROWS + 3), 0.0, f["money"])
    for c, t in enumerate(["K", "r", "T"] + ["Python_" + v for v in model.VARIANTS]
                          + ["Różnica_" + v for v in model.VARIANTS]):
        ws.write(2, c, t, f["h"])
    for idx, row in enumerate(rows):
        r0 = 3 + idx
        R = r0 + 1
        ws.write_number(r0, 0, row["K"], f["money"])
        ws.write_number(r0, 1, row["r"], f["pct2"])
        ws.write_number(r0, 2, row["T"], f["int"])
        for k, v in enumerate(model.VARIANTS):
            ws.write_number(r0, 3 + k, row["net"][v], f["money"])
            W(ws, r0, 8 + k, "=Wyniki!%s%d-%s%d" % (col_name(4 + k), idx + 2, col_name(3 + k), R), 0.0, f["money"])

    wb.close()
    return path


def _write_component(ws, wb, f, r0, R, kind, capcol, bl, path, P):
    """Write one component (a set of blocks) for one pair in the engine sheet."""
    rp = "$D%d" % R
    cap = "$%s%d" % (capcol, R)
    money = f["money"]

    def c(name, n):
        return "%s%d" % (col_name(bl[name] + n), R)

    if kind == "A":
        W(ws, r0, bl["V"], "=%s*(1-par_k_in)" % cap, path["V"][0], money)
        W(ws, r0, bl["B"], "=%s" % cap, path["B"][0], money)
        for n in range(1, NY):
            vp, bp = c("V", n - 1), c("B", n - 1)
            d = "IF(%s>0,par_s*%s*%s,0)" % (rp, rp, vp)
            W(ws, r0, bl["V"] + n, "=MAX(0,%s*(1+%s)-par_Belka*%s-IF(%s>0,par_F,0))" % (vp, rp, d, vp),
              path["V"][n], money)
            W(ws, r0, bl["B"] + n, "=%s+%s-par_Belka*%s" % (bp, d, d), path["B"][n], money)
    elif kind == "OKI":
        W(ws, r0, bl["V"], "=%s*(1-par_k_in)" % cap, path["V"][0], money)
        ws.write_number(r0, bl["Tax"], 0, money)
        for n in range(1, NY):
            vp = c("V", n - 1)
            vavg = "%s*(1+par_w*%s)" % (vp, rp)
            W(ws, r0, bl["Tax"] + n,
              "=Lata!$B$%d*MAX(0,(1-par_q)*(%s)+MAX(0,par_q*(%s)-Lata!$C$%d))" % (n + 2, vavg, vavg, n + 2),
              path["Tax"][n], money)
            W(ws, r0, bl["V"] + n, "=MAX(0,%s*(1+%s)-%s-IF(%s>0,par_F,0))" % (vp, rp, c("Tax", n), vp),
              path["V"][n], money)
    else:  # IKE + brokerage
        W(ws, r0, bl["VB"], "=%s*(1-par_k_in)" % cap, path["VB"][0], money)
        W(ws, r0, bl["BB"], "=%s" % cap, path["BB"][0], money)
        for name in ("VI", "CI", "cn", "wpl"):
            ws.write_number(r0, bl[name], 0, money)
        for n in range(1, NY):
            vbp, bbp, vip, cip = c("VB", n - 1), c("BB", n - 1), c("VI", n - 1), c("CI", n - 1)
            cn, wpl = c("cn", n), c("wpl", n)
            frac = "IF(%s>0,%s/%s,0)" % (vbp, cn, vbp)
            vbr = "(%s-%s)" % (vbp, cn)
            bbr = "%s*(1-%s)" % (bbp, frac)
            d = "IF(%s>0,par_s*%s*%s,0)" % (rp, rp, vbr)
            W(ws, r0, bl["cn"] + n, "=MIN(Lata!$D$%d,%s)" % (n + 2, vbp), path["cn"][n], money)
            W(ws, r0, bl["wpl"] + n, "=%s-par_Belka*%s*MAX(0,%s-%s)" % (cn, frac, vbp, bbp), path["wpl"][n], money)
            W(ws, r0, bl["VI"] + n, "=(%s+%s)*(1+%s)-IF(%s+%s>0,par_F,0)" % (vip, wpl, rp, vip, wpl),
              path["VI"][n], money)
            W(ws, r0, bl["CI"] + n, "=%s+%s" % (cip, wpl), path["CI"][n], money)
            W(ws, r0, bl["VB"] + n, "=MAX(0,%s*(1+%s)-par_Belka*%s-IF(%s>0,par_F,0))" % (vbr, rp, d, vbr),
              path["VB"][n], money)
            W(ws, r0, bl["BB"] + n, "=%s+%s-par_Belka*%s" % (bbr, d, d), path["BB"][n], money)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT
    print(build(out))
