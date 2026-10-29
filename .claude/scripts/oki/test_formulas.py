#!/usr/bin/env python3
# Checks the formulas build_xlsx.py writes against the Python model, without
# Excel and without xlsxwriter: the workbook is recorded by a stub, and every
# formula it can read (arithmetic, MAX, MIN, IF, AND, ABS, ROUNDDOWN, INDEX,
# cell and range references, named cells) is evaluated from the other cells
# and compared with the value model.py computed for it. Formulas that need
# more (SUMPRODUCT, COUNTIFS, MINIFS, MATCH, text joins) are counted as
# skipped - Excel is the judge of those.
#
#   python3 .claude/scripts/oki/test_formulas.py

import ast
import math
import os
import re
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def col_to_name(n):
    s = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def name_to_col(s):
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


class Sheet:
    def __init__(self, book, name):
        self.book, self.name = book, name

    def write_number(self, r, c, v, fmt=None):
        self.book.cells[(self.name, r, c)] = ("v", v)

    def write(self, r, c, v, fmt=None):
        self.book.cells[(self.name, r, c)] = ("v", v)

    def write_blank(self, r, c, v=None, fmt=None):
        pass

    def write_formula(self, r, c, formula, fmt=None, value=0):
        self.book.cells[(self.name, r, c)] = ("f", formula, value)

    def __getattr__(self, name):  # set_column, freeze_panes, conditional_format ...
        return lambda *a, **k: None


class Book:
    def __init__(self, path=None, options=None):
        self.cells, self.names, self.sheets = {}, {}, []

    def add_worksheet(self, name):
        self.sheets.append(name)
        return Sheet(self, name)

    def add_format(self, *a, **k):
        return None

    def define_name(self, name, ref):
        self.names[name] = ref

    def close(self):
        pass


BOOK = {}


def make_book(path=None, options=None):
    b = Book(path, options)
    BOOK["b"] = b
    return b


stub = types.ModuleType("xlsxwriter")
stub.Workbook = make_book
util = types.ModuleType("xlsxwriter.utility")
util.xl_col_to_name = col_to_name
stub.utility = util
sys.modules["xlsxwriter"] = stub
sys.modules["xlsxwriter.utility"] = util
import build_xlsx  # noqa: E402


class Unsupported(Exception):
    pass


def flat(x):
    if isinstance(x, (list, tuple)):
        return [y for item in x for y in flat(item)]
    return [x]


REF = re.compile(r"(?<![\w.])(?:(\w+)!)?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?(?![\w(])")
NAME = re.compile(r"\bpar_\w+")
UNSUPPORTED = ("SUMPRODUCT", "COUNTIFS", "COUNTIF", "MINIFS", "MATCH", "COUNT(", "&", "{")


class Evaluator:
    def __init__(self, book):
        self.b, self.memo = book, {}

    def cell(self, sheet, r, c):
        key = (sheet, r, c)
        if key in self.memo:
            return self.memo[key]
        cell = self.b.cells.get(key)
        if cell is None:
            val = ""
        elif cell[0] == "v":
            val = cell[1]
        else:
            val = self.eval_formula(cell[1], sheet)
        self.memo[key] = val
        return val

    def eval_formula(self, formula, sheet):
        if any(u in formula for u in UNSUPPORTED):
            raise Unsupported(formula)
        text = formula[1:]
        text = re.sub(r"(?<![<>=!])=(?!=)", "==", text.replace("<>", "!="))
        text = text.replace("^", "**")

        def ref(m):
            sh = m.group(1) or sheet
            c1, r1 = name_to_col(m.group(2)), int(m.group(3)) - 1
            if m.group(4):
                return "RG(%r,%d,%d,%d,%d)" % (sh, r1, c1, int(m.group(5)) - 1, name_to_col(m.group(4)))
            return "CELL(%r,%d,%d)" % (sh, r1, c1)

        text = REF.sub(ref, text)
        text = NAME.sub(lambda m: "NM(%r)" % m.group(0), text)
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError:
            raise Unsupported(formula)

        class IfLazy(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id == "IF":
                    cond, a, b = node.args
                    return ast.IfExp(test=cond, body=a, orelse=b)
                return node

        tree = ast.fix_missing_locations(IfLazy().visit(tree))
        env = {
            "CELL": self.cell,
            "RG": lambda sh, r1, c1, r2, c2: [[self.cell(sh, r, c) for c in range(c1, c2 + 1)]
                                              for r in range(r1, r2 + 1)],
            "NM": self.name,
            "MAX": lambda *a: max(flat(a)), "MIN": lambda *a: min(flat(a)),
            "AND": lambda *a: all(a), "ABS": abs,
            "ROUNDDOWN": lambda x, n: math.floor(x * 10 ** n + 1e-9) / 10 ** n,
            "INDEX": lambda rg, r, c=1: rg[int(r) - 1][int(c) - 1],
        }
        try:
            return eval(compile(tree, "<f>", "eval"), env)
        except NameError as e:
            raise Unsupported("%s: %s" % (formula, e))

    def name(self, nm):
        m = re.match(r"=(\w+)!\$([A-Z]+)\$(\d+)", self.b.names[nm])
        return self.cell(m.group(1), int(m.group(3)) - 1, name_to_col(m.group(2)))


class FormulasMatchModel(unittest.TestCase):
    def test_every_readable_formula_equals_its_python_value(self):
        sys.setrecursionlimit(50_000)
        build_xlsx.build("unused.xlsx")
        book = BOOK["b"]
        ev = Evaluator(book)
        checked = skipped = 0
        bad = []
        for (sheet, r, c), cell in sorted(book.cells.items(), key=lambda kv: (book.sheets.index(kv[0][0]),
                                                                                kv[0][1], kv[0][2])):
            if cell[0] != "f":
                continue
            try:
                got = ev.cell(sheet, r, c)
            except Unsupported:
                skipped += 1
                continue
            want = cell[2]
            checked += 1
            if isinstance(want, str) or isinstance(got, str):
                ok = got == want
            else:
                ok = abs(got - want) <= 1e-6 * max(1.0, abs(want))
            if not ok:
                bad.append((sheet, col_to_name(c) + str(r + 1), cell[1], got, want))
        print("formulas checked: %d, skipped (need Excel): %d" % (checked, skipped))
        self.assertGreater(checked, 100_000)
        self.assertEqual(bad[:5], [])


if __name__ == "__main__":
    unittest.main()
