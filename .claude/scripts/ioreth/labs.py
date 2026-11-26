#!/usr/bin/env python3
# I.O.R.E.T.H. — the lab results store, standard library only (the MCP wrapper
# is mcp_server.py).
#
# One examination is saved as two things written together or not at all:
#   brain/core/health/labs/reports/<date>_<provider>.md   the transcription
#   brain/db/labs.db                                      its rows, linking to it
# The table in the file and the rows come from the same data. The original
# PDF or image is never read, copied or stored here.
#
# Numbers are parsed here from the printed strings, and what is out of range or
# changed is computed here — not by the model. Nothing is deleted: a correction
# is a new report and the old row gets `superseded_by` (the old file stays as it
# was; the new one names it in `supersedes:`).

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[3]
REPORTS_DIR = "core/health/labs/reports"

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS reports (
        id               INTEGER PRIMARY KEY,
        exam_date        TEXT NOT NULL,
        result_date      TEXT,
        provider         TEXT NOT NULL,
        collection_point TEXT,
        identifiers      TEXT NOT NULL,  -- JSON: [{"label": …, "value": …}]
        kind             TEXT NOT NULL,  -- tabular | descriptive
        transcript       TEXT NOT NULL,  -- path relative to brain/
        fingerprint      TEXT NOT NULL,
        saved_at         TEXT NOT NULL,
        superseded_by    INTEGER REFERENCES reports(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS results (
        id        INTEGER PRIMARY KEY,
        report_id INTEGER NOT NULL REFERENCES reports(id),
        material  TEXT NOT NULL,
        param     TEXT NOT NULL,  -- the same key for the same test across labs
        name      TEXT NOT NULL,  -- as printed
        value     TEXT NOT NULL,  -- as printed
        value_num REAL,
        comparator TEXT,          -- < <= > >=
        unit      TEXT,
        ref       TEXT,           -- the reference range of this printout
        flag      TEXT            -- as printed
    )
    """,
)

REPORT_KEYS = {
    "exam_date", "result_date", "provider", "collection_point", "identifiers",
    "results", "text", "attachments", "pages_read", "supersedes",
}
ROW_KEYS = {"material", "param", "name", "value", "unit", "ref", "flag", "uncertain"}
NUMBER = r"[+-]?\d+(?:[.,]\d+)?"
OPERATORS = {"<": "<", "<=": "<=", "≤": "<=", ">": ">", ">=": ">=", "≥": ">="}


class Refused(Exception):
    pass


def brain_path() -> Path:
    raw = ""
    try:
        for line in (PROJECT_DIR / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("BRAIN_PATH="):
                raw = line.partition("=")[2].strip().strip("\"'")
    except OSError:
        pass
    path = Path(os.path.expanduser(raw or "../brain"))
    path = (path if path.is_absolute() else PROJECT_DIR / path).resolve()
    for need in ("db", "core/health"):
        if not (path / need).is_dir():
            raise Refused(f"{path / need} does not exist — BRAIN_PATH wrong or brain/ not initialised")
    return path


# --- printed strings --------------------------------------------------------------

def _float(text: str) -> float:
    return float(text.replace(",", "."))


def parse_value(printed: str) -> tuple[float | None, str | None]:
    """(number, comparator) of a printed value; (None, None) for a word."""
    match = re.fullmatch(rf"\s*(<=|>=|≤|≥|<|>)?\s*({NUMBER})\s*", printed)
    if not match:
        return None, None
    return _float(match[2]), OPERATORS.get(match[1])


def parse_ref(printed: str | None):
    """(low, low_included, high, high_included), or None when the range is not a
    single plain one (words, several categories) — then nothing is judged."""
    if not printed:
        return None
    text = printed.strip().strip("()[] ")
    match = re.fullmatch(rf"({NUMBER})\s*(?:-|–|—|÷|\.\.)\s*({NUMBER})", text)
    if match:
        low, high = _float(match[1]), _float(match[2])
        return (low, True, high, True) if low <= high else None
    match = re.fullmatch(rf"(<=|>=|≤|≥|<|>)\s*({NUMBER})", text)
    if match:
        operator, number = OPERATORS[match[1]], _float(match[2])
        if operator.startswith("<"):
            return (None, True, number, operator == "<=")
        return (number, operator == ">=", None, True)
    return None


def status(value_num: float | None, comparator: str | None, ref: str | None) -> str:
    """below | above | within | unknown — against the printout's own range."""
    bounds = parse_ref(ref)
    if value_num is None or bounds is None:
        return "unknown"
    low, low_in, high, high_in = bounds
    if comparator and comparator.startswith("<"):
        # all that is known: the value is at most value_num
        if low is not None and value_num <= low:
            return "below"
        if high is not None and value_num <= high and (low is None or low <= 0):
            return "within"
        return "unknown"
    if comparator and comparator.startswith(">"):
        if high is not None and value_num >= high:
            return "above"
        if high is None and low is not None and value_num >= low:
            return "within"
        return "unknown"
    if low is not None and (value_num < low or (value_num == low and not low_in)):
        return "below"
    if high is not None and (value_num > high or (value_num == high and not high_in)):
        return "above"
    return "within"


def _unit_key(unit: str | None) -> str:
    return unicodedata.normalize("NFKC", unit or "").replace(" ", "").replace("μ", "u")


# --- the report as it comes in ----------------------------------------------------

def _clean(value, field: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, (str, int, float)):
        raise Refused(f"{field} must be text")
    text = " ".join(str(value).split())
    if required and not text:
        raise Refused(f"{field} is missing")
    return text


def _date(value, field: str, required: bool = False) -> str:
    text = _clean(value, field, required)
    if not text:
        return ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise Refused(f"{field} must be YYYY-MM-DD, got {text!r}")
    try:
        day = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise Refused(f"{field}: {text} is not a real day")
    if day > datetime.now().date():
        raise Refused(f"{field}: {text} is in the future")
    return text


def _is_pesel(digits: str) -> bool:
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    check = (10 - sum(int(d) * w for d, w in zip(digits, weights)) % 10) % 10
    month, day = int(digits[2:4]) % 20, int(digits[4:6])
    return check == int(digits[10]) and 1 <= month <= 12 and 1 <= day <= 31


def _no_pesel(text: str, field: str) -> None:
    if any(_is_pesel(found) for found in re.findall(r"(?<!\d)\d{11}(?!\d)", text)):
        raise Refused(f"{field} holds what looks like a PESEL — replace it with [pominięto]")


def normalise(report: dict) -> dict:
    if not isinstance(report, dict):
        raise Refused("report must be an object")
    unknown = set(report) - REPORT_KEYS
    if unknown:
        raise Refused(f"unknown field(s) in the report: {', '.join(sorted(unknown))}")
    clean = {
        "exam_date": _date(report.get("exam_date"), "exam_date", required=True),
        "result_date": _date(report.get("result_date"), "result_date"),
        "provider": _clean(report.get("provider"), "provider") or "brak",
        "collection_point": _clean(report.get("collection_point"), "collection_point"),
        "pages_read": _clean(report.get("pages_read"), "pages_read"),
        "attachments": [Path(_clean(a, "attachments", True)).name for a in report.get("attachments") or []],
        "text": str(report.get("text") or "").strip(),
        "identifiers": [],
        "results": [],
        "supersedes": int(report.get("supersedes") or 0),
    }
    for item in report.get("identifiers") or []:
        label = _clean(item.get("label"), "identifiers.label", required=True)
        if "pesel" in label.casefold():
            raise Refused("PESEL is never stored — leave that identifier out")
        clean["identifiers"].append({"label": label, "value": _clean(item.get("value"), label, required=True)})
    for number, row in enumerate(report.get("results") or [], start=1):
        unknown = set(row) - ROW_KEYS
        if unknown:
            raise Refused(f"row {number}: unknown field(s) {', '.join(sorted(unknown))}")
        entry = {k: _clean(row.get(k), f"row {number}: {k}", k in ("material", "param", "name", "value"))
                 for k in ("material", "param", "name", "value", "unit", "ref", "flag")}
        entry["material"] = entry["material"].casefold()
        entry["param"] = entry["param"].casefold()
        entry["uncertain"] = bool(row.get("uncertain"))
        clean["results"].append(entry)
    if not clean["results"] and not clean["text"]:
        raise Refused("nothing to save — no results and no text")
    for field in ("text", "provider", "collection_point"):
        _no_pesel(clean[field], field)
    for entry in clean["results"]:
        _no_pesel(entry["name"], "a result's name")
    return clean


def digest(clean: dict) -> str:
    raw = json.dumps(clean, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _fingerprint(clean: dict) -> str:
    """What makes two saves the same examination: date, provider and the results
    (for a descriptive one, the text)."""
    body = sorted(
        (r["material"], r["param"], r["value"], _unit_key(r["unit"])) for r in clean["results"]
    ) or " ".join(clean["text"].split()).casefold()
    raw = json.dumps([clean["exam_date"], clean["provider"].casefold(), body], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


# --- the transcription file -------------------------------------------------------

def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _quoted(text: str) -> str:
    return '"' + text.replace("\\", "").replace('"', "'").replace(" #", " nr ") + '"'


def _source_line(clean: dict) -> str:
    parts = [clean["provider"]]
    parts += [f"{i['label']}: {i['value']}" for i in clean["identifiers"]]
    parts.append(f"data badania {clean['exam_date']}")
    return ", ".join(parts)


def render(clean: dict, saved_at: str, supersedes_path: str = "") -> str:
    lines = [
        "---",
        f"date: {saved_at}",
        f"source: {_quoted(_source_line(clean))}",
        "privacy: private",
        "status: active",
        "tags: [health, lab-results]",
        f"exam_date: {clean['exam_date']}",
    ]
    if supersedes_path:
        lines.append(f"supersedes: {supersedes_path}")
    identifiers = "; ".join(f"{i['label']}: {i['value']}" for i in clean["identifiers"])
    lines += [
        "---",
        "",
        f"# Badanie {clean['exam_date']} — {clean['provider']}",
        "",
        "## Źródło",
        "",
        f"- Placówka / firma: {clean['provider']}",
        f"- Punkt pobrań: {clean['collection_point'] or 'brak'}",
        f"- Numery: {identifiers or 'brak'}",
        f"- Data badania / pobrania: {clean['exam_date']}",
        f"- Data wyniku: {clean['result_date'] or 'brak'}",
        f"- Załączniki (nie są przechowywane): {', '.join(clean['attachments']) or 'brak — tekst z rozmowy'}",
        f"- Przeczytane strony: {clean['pages_read'] or 'nie dotyczy'}",
    ]
    if clean["results"]:
        lines += [
            "",
            f"## Wyniki ({len(clean['results'])} pozycji)",
            "",
            "| Materiał | Parametr | Wynik | Jednostka | Zakres referencyjny | Flaga | Klucz |",
            "|---|---|---|---|---|---|---|",
        ]
        lines += [
            "| " + " | ".join(_cell(r[k]) for k in ("material", "name", "value", "unit", "ref", "flag", "param")) + " |"
            for r in clean["results"]
        ]
    if clean["text"]:
        lines += ["", "## Pozostała treść dokumentu", "", clean["text"]]
    lines += ["", "> Transkrypcja odczytana przez model z załącznika; oryginał ma wystawca.", ""]
    return "\n".join(lines)


# --- the database -----------------------------------------------------------------

def _connect(brain: Path, write: bool = False) -> sqlite3.Connection | None:
    path = brain / "db" / "labs.db"
    if not write and not path.is_file():
        return None
    con = sqlite3.connect(path if write else f"file:{path}?mode=ro", uri=not write, timeout=10)
    con.row_factory = sqlite3.Row
    if write:
        for statement in SCHEMA:
            con.execute(statement)
        con.commit()
    return con


def _superseded(con, report_id: int) -> sqlite3.Row:
    row = con.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone() if con else None
    if row is None:
        raise Refused(f"there is no report {report_id} to supersede")
    if row["superseded_by"]:
        raise Refused(f"report {report_id} is already superseded by {row['superseded_by']}")
    return row


def _duplicate(con, clean: dict) -> None:
    if con is None:
        return
    row = con.execute(
        "SELECT id, transcript FROM reports WHERE fingerprint = ? AND superseded_by IS NULL AND id != ?",
        (_fingerprint(clean), clean["supersedes"]),
    ).fetchone()
    if row:
        raise Refused(f"already saved: report {row['id']} ({row['transcript']}) has the same date, provider and results")


def _warnings(con, clean: dict) -> list[str]:
    notes = [f"niepewny odczyt: {r['name']} = {r['value']}" for r in clean["results"] if r["uncertain"]]
    if clean["provider"] == "brak":
        notes.append("brak placówki / firmy")
    if not clean["identifiers"]:
        notes.append("brak numeru badania / zlecenia")
    if con is None:
        return notes
    wanted = {i["value"] for i in clean["identifiers"]}
    for row in con.execute("SELECT id, provider, identifiers FROM reports WHERE superseded_by IS NULL"):
        shared = wanted & {i["value"] for i in json.loads(row["identifiers"])}
        if shared and row["provider"].casefold() == clean["provider"].casefold() and row["id"] != clean["supersedes"]:
            notes.append(f"numer {', '.join(sorted(shared))} jest już w badaniu {row['id']}")
    return notes


def preview(brain: Path, report: dict) -> str:
    """The file exactly as `save` would write it (but for its timestamp), the
    warnings, and the digest `save` asks for. Writes nothing."""
    clean = normalise(report)
    con = _connect(brain)
    try:
        old = _superseded(con, clean["supersedes"])["transcript"] if clean["supersedes"] else ""
        _duplicate(con, clean)
        notes = _warnings(con, clean)
    finally:
        if con:
            con.close()
    text = render(clean, "<czas zapisu>", old)
    notes_block = "\n".join(f"- {n}" for n in notes) or "- brak"
    return (
        f"digest: {digest(clean)}\n"
        f"pozycji w tabeli: {len(clean['results'])}\n"
        f"uwagi:\n{notes_block}\n\n"
        f"----- plik -----\n{text}"
    )


def _free_path(brain: Path, clean: dict) -> Path:
    plain = unicodedata.normalize("NFKD", clean["provider"].replace("ł", "l").replace("Ł", "L"))
    slug = re.sub(r"[^a-z0-9]+", "-", plain.encode("ascii", "ignore").decode().lower()).strip("-")[:40]
    folder = brain / REPORTS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"{clean['exam_date']}_{slug or 'badanie'}"
    path, number = folder / f"{stem}.md", 2
    while path.exists():
        path, number = folder / f"{stem}_{number}.md", number + 1
    return path


def save(brain: Path, report: dict, expected_digest: str) -> str:
    """Write the transcription and its rows — both or neither."""
    clean = normalise(report)
    if digest(clean) != expected_digest.strip():
        raise Refused("the report differs from the one previewed (digest mismatch) — preview it again and show it to the owner")
    con = _connect(brain, write=True)
    written = None
    try:
        old = _superseded(con, clean["supersedes"]) if clean["supersedes"] else None
        _duplicate(con, clean)
        saved_at = datetime.now().replace(microsecond=0).isoformat()
        path = _free_path(brain, clean)
        relative = path.relative_to(brain).as_posix()
        cursor = con.execute(
            "INSERT INTO reports (exam_date, result_date, provider, collection_point, identifiers, kind, "
            "transcript, fingerprint, saved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (clean["exam_date"], clean["result_date"] or None, clean["provider"], clean["collection_point"] or None,
             json.dumps(clean["identifiers"], ensure_ascii=False),
             "tabular" if clean["results"] else "descriptive", relative, _fingerprint(clean), saved_at),
        )
        report_id = cursor.lastrowid
        for row in clean["results"]:
            number, comparator = parse_value(row["value"])
            con.execute(
                "INSERT INTO results (report_id, material, param, name, value, value_num, comparator, unit, ref, flag) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (report_id, row["material"], row["param"], row["name"], row["value"], number, comparator,
                 row["unit"] or None, row["ref"] or None, row["flag"] or None),
            )
        if old:
            con.execute("UPDATE reports SET superseded_by = ? WHERE id = ?", (report_id, old["id"]))
        with open(path, "x", encoding="utf-8") as fh:
            written = path
            fh.write(render(clean, saved_at, old["transcript"] if old else ""))
        con.commit()
    except BaseException:
        con.rollback()
        if written:
            written.unlink(missing_ok=True)
        raise
    finally:
        con.close()
    replaced = f"\nsupersedes report {old['id']}" if old else ""
    return (
        f"saved report {report_id}: {len(clean['results'])} result(s){replaced}\n"
        f"paths for the commit:\n  {relative}\n  db/labs.db"
    )


# --- fixed reads ------------------------------------------------------------------

def _source_of(row) -> str:
    numbers = "; ".join(f"{i['label']}: {i['value']}" for i in json.loads(row["identifiers"]))
    return f"{row['provider']} ({numbers or 'brak numeru'})"


def _table(header: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell("" if v is None else str(v)) for v in row) + " |" for row in rows]
    return "\n".join(out)


def list_reports(brain: Path) -> str:
    con = _connect(brain)
    if con is None:
        return "no results saved yet"
    try:
        rows = con.execute(
            "SELECT r.*, (SELECT COUNT(*) FROM results WHERE report_id = r.id) AS items "
            "FROM reports r WHERE superseded_by IS NULL ORDER BY exam_date, id"
        ).fetchall()
    finally:
        con.close()
    return _table(
        ["id", "exam_date", "result_date", "source", "kind", "items", "transcript"],
        [[r["id"], r["exam_date"], r["result_date"], _source_of(r), r["kind"], r["items"], r["transcript"]] for r in rows],
    )


ACTIVE = (
    "SELECT x.*, r.exam_date, r.provider, r.identifiers FROM results x "
    "JOIN reports r ON r.id = x.report_id WHERE r.superseded_by IS NULL"
)


def history(brain: Path, param: str = "") -> str:
    """Without `param`: the keys stored. With it: every value over time."""
    con = _connect(brain)
    if con is None:
        return "no results saved yet"
    try:
        rows = con.execute(ACTIVE + " ORDER BY x.material, x.param, r.exam_date, r.id, x.id").fetchall()
    finally:
        con.close()
    if not param.strip():
        keys: dict = {}
        for r in rows:
            keys.setdefault((r["material"], r["param"]), []).append(r)
        return _table(
            ["material", "param", "name (latest)", "unit (latest)", "values", "last exam"],
            [[m, p, v[-1]["name"], v[-1]["unit"], len(v), v[-1]["exam_date"]] for (m, p), v in keys.items()],
        )
    wanted = param.strip().casefold()
    found = [r for r in rows if r["param"] == wanted]
    if not found:
        return f"no values for `{wanted}` — call history without a param for the stored keys"
    return _table(
        ["exam_date", "material", "value", "unit", "ref (that printout)", "status", "flag", "source", "report"],
        [[r["exam_date"], r["material"], r["value"], r["unit"], r["ref"],
          status(r["value_num"], r["comparator"], r["ref"]), r["flag"], _source_of(r), r["report_id"]] for r in found],
    )


def compare(brain: Path, report_id: int = 0) -> str:
    """One report (the latest by exam date when 0), each result with its status
    and set against the previous value of the same key and material."""
    con = _connect(brain)
    if con is None:
        return "no results saved yet"
    try:
        if report_id:
            report = con.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        else:
            report = con.execute(
                "SELECT * FROM reports WHERE superseded_by IS NULL AND kind = 'tabular' "
                "ORDER BY exam_date DESC, id DESC LIMIT 1"
            ).fetchone()
        if report is None:
            return "no such report"
        rows = con.execute("SELECT * FROM results WHERE report_id = ? ORDER BY id", (report["id"],)).fetchall()
        out = []
        for r in rows:
            previous = con.execute(
                ACTIVE + " AND x.param = ? AND x.material = ? AND r.exam_date < ? "
                "ORDER BY r.exam_date DESC, r.id DESC LIMIT 1",
                (r["param"], r["material"], report["exam_date"]),
            ).fetchone()
            change, before = "", ["", "", ""]
            if previous:
                before = [previous["exam_date"], previous["value"], previous["ref"]]
                if _unit_key(previous["unit"]) != _unit_key(r["unit"]):
                    change = f"different unit ({previous['unit'] or 'none'}) — not compared"
                elif (r["value_num"] is not None and previous["value_num"] is not None
                      and not r["comparator"] and not previous["comparator"]):
                    delta = r["value_num"] - previous["value_num"]
                    change = f"{delta:+.4g}"
                    if previous["value_num"]:
                        change += f" ({delta / abs(previous['value_num']):+.0%})"
                else:
                    change = "not numeric — compare by eye"
            out.append([r["material"], r["param"], r["value"], r["unit"], r["ref"],
                        status(r["value_num"], r["comparator"], r["ref"]), r["flag"], *before, change])
    finally:
        con.close()
    note = f"\nSUPERSEDED by report {report['superseded_by']}" if report["superseded_by"] else ""
    head = (
        f"report {report['id']} of {report['exam_date']} — {_source_of(report)}\n"
        f"transcript: {report['transcript']}{note}"
    )
    return head + "\n\n" + _table(
        ["material", "param", "value", "unit", "ref", "status", "flag",
         "previous date", "previous value", "previous ref", "change"],
        out,
    )
