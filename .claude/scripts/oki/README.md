# OKI account simulation

A model of five ways to hold a lump sum — plain brokerage account (A), OKI (B),
IKE + brokerage (C), OKI + brokerage (D), OKI + IKE + brokerage (E) — over
800 configurations (capital 100 k–1 M, rate −4%…10%, horizon 5–50 years), and
a workbook of live Excel formulas to play with it. The specification is
section 8 of the owner's dossier in `brain/knowledge/projects/` (not in this
repo). Not a script of an agent: run by hand.

| File | What it is |
|---|---|
| `model.py` | the reference model, plain Python; every unverified point (q, w, π, rates — the dossier's V1–V7) is a parameter |
| `test_model.py` | the dossier's cases T1–T10 against the model |
| `build_xlsx.py` | writes `output/oki-symulacje.xlsx` (gitignored); needs `xlsxwriter` (`requirements.txt`) |
| `test_formulas.py` | evaluates the workbook's formulas (no Excel, no xlsxwriter) and compares them with the model's values |
| `analysis.py` | the dossier's hypotheses H1–H4, the example configurations and the sensitivity scenarios, printed from the model |

```
python3 .claude/scripts/oki/test_model.py
python3 .claude/scripts/oki/test_formulas.py      # about a minute
pip install -r .claude/scripts/oki/requirements.txt   # once
python3 .claude/scripts/oki/build_xlsx.py
```

Every formula in the workbook is stored with the value Python computed, so the
file shows numbers before Excel recalculates; Excel recalculates on opening.
After that the sheet `Kontrola_Python` shows the largest gap between the
formulas and the Python values, and `Testy` runs T1–T10 in the sheet. The
expected values of T1–T4 hold for the default parameters only; with other
parameters the sheets say `N/D`. `MINIFS` needs Excel 2019 or newer.
