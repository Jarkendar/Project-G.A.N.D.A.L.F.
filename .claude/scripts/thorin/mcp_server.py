#!/usr/bin/env python3
# T.H.O.R.I.N. — Treasury Holdings & Official Reports INgest.
#
# The three things the finance agents would otherwise need a shell for, as MCP
# tools:
#
#   read_export     a myFund XML export in brain/current/inbox/ → the net
#                   position per ticker (the arithmetic of /ingest-finance
#                   step 3, done here so no model adds up transactions).
#                   Without a file name: the exports waiting in the inbox.
#                   Reads only.
#   archive_export  the end of an ingest: writes the readable .md copy of the
#                   export into current/inbox/_processed/ and moves the source
#                   file there. One named file, one direction, never
#                   overwriting an archived source.
#   edgar_reports   one US ticker → its 10-K / 10-Q filings since a date with
#                   the key figures, from SEC EDGAR (which wants a descriptive
#                   User-Agent that WebFetch cannot set). Used by G.L.O.I.N.
#                   Only the ticker's CIK goes out — the ticker is resolved
#                   against SEC's full ticker list, fetched whole.
#
# read_export and archive_export belong to the Thorin sub-agent, edgar_reports
# to Gloin, his treasurer.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.(xml|md)$")
EXPORT_HINT_RE = re.compile(r"myfund|portfel", re.IGNORECASE)
TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.-]{0,9}$")
OPEN_THRESHOLD = Decimal("0.001")
MAX_EXPORT_BYTES = 20 * 1024 * 1024

DEFAULT_USER_AGENT = "gandalf-personal-assistant/1.0"
HTTP_TIMEOUT_S = 40
EDGAR_PAUSE_S = 0.25
MAX_FILINGS = 60
FORMS = ("10-K", "10-Q")
# Metric → (taxonomy concepts tried in order, unit, True if measured over a period).
METRICS = (
    ("Revenue", ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"), "USD", True),
    ("Net income", ("NetIncomeLoss",), "USD", True),
    ("EPS (basic)", ("EarningsPerShareBasic",), "USD/shares", True),
    ("Total assets", ("Assets",), "USD", False),
    ("Long-term debt", ("LongTermDebt",), "USD", False),
    ("Short-term borrowings", ("ShortTermBorrowings",), "USD", False),
    ("Operating cash flow", ("NetCashProvidedByUsedInOperatingActivities",), "USD", True),
)

server = MCPServer(
    name="thorin",
    log_level="WARNING",
    instructions=(
        "Tools of the finance agents: reading and archiving a myFund portfolio export "
        "(T.H.O.R.I.N.) and fetching a company's filings from SEC EDGAR (G.L.O.I.N.). A "
        "portfolio export is the owner's private data — hand an ingest to the Thorin "
        "sub-agent rather than calling these tools yourself."
    ),
)

_ticker_map: dict[str, tuple[int, str]] = {}


class Refused(Exception):
    pass


def _env(key: str) -> str:
    raw = ""
    try:
        for line in (PROJECT_DIR / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line.startswith(key + "="):
                raw = line.partition("=")[2].strip().strip("\"'")
    except OSError:
        pass
    return raw


def _inbox() -> Path:
    brain = Path(os.path.expanduser(_env("BRAIN_PATH") or "../brain"))
    brain = (brain if brain.is_absolute() else PROJECT_DIR / brain).resolve()
    inbox = brain / "current" / "inbox"
    if not inbox.is_dir():
        raise Refused(f"{inbox} does not exist — BRAIN_PATH wrong or brain/ not initialised")
    return inbox


def _source(inbox: Path, filename: str) -> Path:
    if not NAME_RE.match(filename):
        raise Refused(f"{filename!r} is not a plain .xml or .md file name (no folders)")
    if not EXPORT_HINT_RE.search(filename):
        raise Refused(f"{filename} is not a myFund export — its name holds neither 'myfund' nor 'portfel'")
    path = inbox / filename
    if path.is_symlink() or not path.is_file():
        raise Refused(f"{filename} is not a file in current/inbox/")
    if path.stat().st_size > MAX_EXPORT_BYTES:
        raise Refused(f"{filename} is larger than {MAX_EXPORT_BYTES // (1024 * 1024)} MB")
    return path


def _candidates(inbox: Path) -> list[str]:
    return sorted(
        p.name for p in inbox.iterdir()
        if p.is_file() and p.suffix.lower() in (".xml", ".md") and EXPORT_HINT_RE.search(p.name)
    )


def _num(text: str | None) -> Decimal:
    try:
        return Decimal((text or "").strip().replace(",", "."))
    except InvalidOperation:
        raise Refused(f"not a number in the export: {text!r}")


def _parse(path: Path) -> dict:
    """The net position per ticker — /ingest-finance step 3."""
    try:
        root = ET.fromstring(path.read_bytes())
    except ET.ParseError as exc:
        raise Refused(f"{path.name} is not well-formed XML ({exc})")
    rows, skipped = [], 0
    for op in root.iter("operacje"):
        ticker = (op.findtext("TICKER") or "").strip()
        day = (op.findtext("DATA") or "").strip()
        if not ticker or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            skipped += 1
            continue
        rows.append({
            "date": day,
            "time": (op.findtext("CZAS") or "").strip(),
            "ticker": ticker,
            "type": (op.findtext("TYP") or "").strip(),
            "qty": _num(op.findtext("LICZBAJEDNOSTEK")),
            "price": _num(op.findtext("CENA")),
            "currency": (op.findtext("WALUTA") or "").strip(),
        })
    if not rows:
        raise Refused(f"{path.name} holds no <operacje> transactions — not a myFund portfolio export, or a format this tool does not know")
    rows.sort(key=lambda r: (r["date"], r["time"]))
    positions: dict[str, dict] = {}
    for r in rows:
        p = positions.setdefault(r["ticker"], {
            "qty": Decimal(0), "buy_cost": Decimal(0), "buy_qty": Decimal(0),
            "first_buy": None, "last_sell": None, "currencies": [],
        })
        p["qty"] += r["qty"]
        if r["qty"] > 0:
            p["buy_cost"] += r["qty"] * r["price"]
            p["buy_qty"] += r["qty"]
            p["first_buy"] = min(p["first_buy"] or r["date"], r["date"])
        else:
            p["last_sell"] = max(p["last_sell"] or r["date"], r["date"])
        if r["currency"] and r["currency"] not in p["currencies"]:
            p["currencies"].append(r["currency"])
    for p in positions.values():
        p["avg_buy"] = p["buy_cost"] / p["buy_qty"] if p["buy_qty"] else None
    types: dict[str, int] = {}
    for r in rows:
        types[r["type"]] = types.get(r["type"], 0) + 1
    return {
        "portfolio": (root.findtext("settings/nazwaBazy") or "").strip(),
        "base_currency": (root.findtext("settings/walutaBazowa") or "").strip(),
        "rows": rows,
        "skipped": skipped,
        "types": types,
        "open": {t: p for t, p in sorted(positions.items()) if p["qty"] > OPEN_THRESHOLD},
        "closed": {t: p for t, p in sorted(positions.items()) if p["qty"] <= OPEN_THRESHOLD},
    }


def _f(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _table(header: list[str], lines: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(line) + " |" for line in lines]
    return "\n".join(out)


def _open_table(data: dict) -> str:
    return _table(
        ["Ticker", "Ilość", "Śr. cena zakupu", "Waluta", "First buy"],
        [[t, _f(p["qty"]), _f(p["avg_buy"]), "/".join(p["currencies"]), p["first_buy"] or "n/a"]
         for t, p in data["open"].items()],
    )


def _closed_table(data: dict) -> str:
    return _table(
        ["Ticker", "Śr. cena zakupu", "Waluta", "First buy", "Last sell"],
        [[t, _f(p["avg_buy"]), "/".join(p["currencies"]), p["first_buy"] or "n/a", p["last_sell"] or "n/a"]
         for t, p in data["closed"].items()],
    )


def _stamp(path: Path) -> tuple[str, str]:
    """(export day, time of day) — the day from the file name, else the file's own."""
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    found = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    day = modified.strftime("%Y-%m-%d")
    if found:
        try:
            date.fromisoformat(found.group(1))
            day = found.group(1)
        except ValueError:
            pass
    return day, modified.strftime("%H:%M:%S")


def _markdown(path: Path, data: dict) -> str:
    day, clock = _stamp(path)
    named = re.match(r"\d{4}-\d{2}-\d{2}_myfund_(.+)\.xml$", path.name, re.IGNORECASE)
    slug = (named.group(1) if named else data["portfolio"] or path.stem).lower()
    slug = re.sub(r"[^a-z0-9-]+", "-", slug).strip("-") or "portfel"
    label = data["portfolio"] or slug
    history = _table(
        ["Data", "Ticker", "Typ", "Ilość", "Cena"],
        [[r["date"], r["ticker"], r["type"], _f(r["qty"]), _f(r["price"])] for r in data["rows"]],
    )
    return (
        "---\n"
        f"date: {day}T{clock}\n"
        "source: myfund-export\n"
        "privacy: private\n"
        "status: active\n"
        f"tags: [finance, myFund, {slug}]\n"
        f"title: \"myFund {label} — eksport {day}\"\n"
        "---\n\n"
        f"# myFund {label} — eksport {day}\n\n"
        f"## Otwarte pozycje ({len(data['open'])})\n\n{_open_table(data)}\n\n"
        f"## Zamknięte pozycje ({len(data['closed'])})\n\n{_closed_table(data)}\n\n"
        f"## Historia transakcji\n\n{history}\n"
    )


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def read_export(filename: str = "") -> str:
    """Without `filename`: the myFund exports waiting in brain/current/inbox/
    (.xml or .md whose name contains `myfund` or `portfel`). With one — a plain
    file name, no folders — the positions computed from that XML export: quantity
    held, average buy price, currency, first buy and last sell per ticker, open
    and closed apart. Quantities in the export are signed, sells negative; the
    average is over buys only. Nothing is written. A `.md` export is already a
    positions table — `Read` it instead."""
    try:
        inbox = _inbox()
        if not filename.strip():
            found = _candidates(inbox)
            if not found:
                return "THORIN: no myFund export in current/inbox/ — nothing to do."
            return "THORIN: exports waiting in current/inbox/:\n" + "\n".join(f"  {name}" for name in found)
        path = _source(inbox, filename.strip())
        if path.suffix.lower() == ".md":
            return f"THORIN: {path.name} is already a converted export — Read {path} for its tables."
        data = _parse(path)
        days = [r["date"] for r in data["rows"]]
        mixed = [t for group in (data["open"], data["closed"]) for t, p in group.items() if len(p["currencies"]) > 1]
        notes = []
        if mixed:
            notes.append(f"transactions in more than one currency, average not comparable: {', '.join(mixed)}")
        if data["skipped"]:
            notes.append(f"{data['skipped']} record(s) without a ticker or a date left out")
        return (
            f"THORIN: {path.name} — portfolio \"{data['portfolio'] or 'unnamed'}\", base currency "
            f"{data['base_currency'] or 'n/a'}, {len(data['rows'])} transactions "
            f"({min(days)} → {max(days)}).\n"
            f"source: {path}\n"
            f"transaction types: {', '.join(f'{k} {v}' for k, v in sorted(data['types'].items()))}\n\n"
            f"open positions ({len(data['open'])}):\n{_open_table(data)}\n\n"
            f"closed positions ({len(data['closed'])}):\n{_closed_table(data)}"
            + ("\n\nnotes:\n" + "\n".join(f"  - {n}" for n in notes) if notes else "")
        )
    except (Refused, OSError) as exc:
        return f"THORIN: refused — {exc}"


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def archive_export(filename: str) -> str:
    """The last step of an ingest: move one processed export from
    brain/current/inbox/ to current/inbox/_processed/, and for an XML export
    write its readable `.md` copy (open and closed positions, transaction
    history) beside it there. Refused if a file of the same name is already
    archived. Returns the paths now in `_processed/`, for the commit."""
    try:
        inbox = _inbox()
        path = _source(inbox, filename.strip())
        processed = inbox / "_processed"
        target = processed / path.name
        if target.exists():
            raise Refused(f"_processed/{path.name} already exists — an archived export is never overwritten")
        written = []
        text = _markdown(path, _parse(path)) if path.suffix.lower() == ".xml" else None
        processed.mkdir(exist_ok=True)
        if text is not None:
            copy = processed / (path.stem + ".md")
            copy.write_text(text, encoding="utf-8")
            written.append(copy)
        path.rename(target)
        written.append(target)
        return (
            f"THORIN: archived {path.name} — current/inbox/ no longer holds it.\n"
            + "\n".join(f"  {p}" for p in written)
        )
    except (Refused, OSError) as exc:
        return f"THORIN: refused — {exc}"


def _get(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": _env("SEC_USER_AGENT") or DEFAULT_USER_AGENT})
    time.sleep(EDGAR_PAUSE_S)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        hint = " (SEC refused the User-Agent, or the request rate — see SEC_USER_AGENT in .claude/gandalf.env)" if exc.code == 403 else ""
        raise Refused(f"EDGAR answered {exc.code} for {url}{hint}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise Refused(f"EDGAR could not be read at {url}: {exc}")


def _cik(ticker: str) -> tuple[int, str] | None:
    # SEC's full ticker list is served only to a User-Agent that names a contact
    # address (SEC_USER_AGENT). Without one, ask the full-text search, whose
    # entity names carry the tickers: "NAME  (DLR, DLR-PJ)  (CIK 0001297996)".
    if _env("SEC_USER_AGENT"):
        if not _ticker_map:
            for row in _get("https://www.sec.gov/files/company_tickers.json").values():
                _ticker_map[str(row["ticker"]).upper()] = (int(row["cik_str"]), str(row["title"]))
        return _ticker_map.get(ticker)
    doc = _get(f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&forms=10-K,10-Q")
    buckets = (((doc.get("aggregations") or {}).get("entity_filter") or {}).get("buckets")) or []
    for bucket in buckets:
        found = re.fullmatch(r"(.+?)\s+\(([^()]+)\)\s+\(CIK (\d{10})\)", str(bucket.get("key", "")))
        if found and ticker in [t.strip().upper() for t in found.group(2).split(",")]:
            return int(found.group(3)), found.group(1).strip()
    return None


def _filings(cik: int, since: str) -> list[dict]:
    doc = _get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    batches = [doc["filings"]["recent"]]
    # `recent` holds the last ~1000 filings; older ones are paged by date range.
    for page in doc["filings"].get("files", []):
        if page.get("filingTo", "") >= since:
            batches.append(_get(f"https://data.sec.gov/submissions/{page['name']}"))
    out = {}
    for batch in batches:
        for form, filed, period, accession in zip(
            batch["form"], batch["filingDate"], batch["reportDate"], batch["accessionNumber"]
        ):
            if form in FORMS and filed >= since and period:
                out[accession] = {"form": form, "filed": filed, "period": period, "accession": accession}
    return sorted(out.values(), key=lambda f: f["period"])


def _file_key(form: str, period: str) -> str:
    year, month = period[:4], int(period[5:7])
    return f"{year}-annual.md" if form == "10-K" else f"{year}-Q{(month - 1) // 3 + 1}.md"


def _short(value: float, unit: str) -> str:
    if unit != "USD":
        return f"${value:.2f}"
    sign, size = ("-" if value < 0 else ""), abs(value)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if size >= limit:
            return f"{sign}${size / limit:.2f}{suffix}"
    return f"{sign}${size:.0f}"


def _fact(facts: dict, concepts: tuple, unit: str, period_metric: bool, filing: dict) -> str:
    for concept in concepts:
        entries = (((facts.get("us-gaap") or {}).get(concept) or {}).get("units") or {}).get(unit) or []
        hits = [e for e in entries if e.get("end") == filing["period"] and e.get("form") == filing["form"]]
        own = [e for e in hits if e.get("accn") == filing["accession"]]
        hits = own or hits
        if not hits:
            continue
        if period_metric:
            def days(entry):
                try:
                    return (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days
                except (KeyError, ValueError):
                    return 0
            # A 10-Q reports the quarter and the year to date under one period end:
            # take the quarter. A 10-K: the full year.
            pick = max(hits, key=days) if filing["form"] == "10-K" else min(hits, key=lambda e: days(e) or 10**6)
            span = f"{pick.get('start', '?')} → {pick['end']}"
            if filing["form"] == "10-Q" and days(pick) > 100:
                span += ", year to date — the filing gives no single-quarter figure"
        else:
            pick = max(hits, key=lambda e: e.get("filed", ""))
            span = f"as of {pick['end']}"
        return f"{_short(pick['val'], unit)} (exact: {pick['val']} {unit}; {span}; {concept})"
    return "n/a"


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
def edgar_reports(ticker: str, since: str) -> str:
    """The 10-K and 10-Q filings of one US-listed company filed on or after `since`
    (YYYY-MM-DD), from SEC EDGAR, each with the report file name it belongs in
    (`YYYY-QQ.md` / `YYYY-annual.md`, by period end) and its key figures: revenue,
    net income, basic EPS, total assets, debt, operating cash flow. A figure the
    filing's XBRL does not carry is `n/a`. `NO MATCH` means EDGAR does not list
    the ticker — it is not a US issuer. Public data; nothing but the company's
    CIK is sent."""
    try:
        ticker = ticker.strip().upper()
        if not TICKER_RE.match(ticker):
            raise Refused(f"{ticker!r} is not a ticker")
        try:
            date.fromisoformat(since)
        except ValueError:
            raise Refused("since must be YYYY-MM-DD")
        found = _cik(ticker)
        if not found:
            return f"THORIN: NO MATCH — EDGAR lists no company under the ticker {ticker}."
        cik, title = found
        filings = _filings(cik, since)
        head = f"THORIN: {ticker} — {title}, CIK {cik:010d}. 10-K / 10-Q filed since {since}: {len(filings)}"
        if not filings:
            return head + "."
        dropped = max(0, len(filings) - MAX_FILINGS)
        filings = filings[-MAX_FILINGS:]
        doc = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
        facts, name = doc.get("facts") or {}, doc.get("entityName") or title
        blocks = []
        for filing in filings:
            lines = [
                f"file: {_file_key(filing['form'], filing['period'])}",
                f"  form: {filing['form']} | period end: {filing['period']} | filed: {filing['filed']} | accession: {filing['accession']}",
            ]
            figures = [(label, _fact(facts, concepts, unit, period, filing)) for label, concepts, unit, period in METRICS]
            if all(value == "n/a" for _, value in figures):
                # EDGAR's XBRL data trails a new filing by days or weeks.
                lines.append("  NO FIGURES YET — EDGAR has not published this filing's data. Write no file for it; a later run picks it up.")
            else:
                lines += [f"  {label}: {value}" for label, value in figures]
            blocks.append("\n".join(lines))
        return (
            f"{head}.\ncompany name: {name}\n"
            + (f"(only the {MAX_FILINGS} most recent are listed; {dropped} older ones left out)\n" if dropped else "")
            + "\n" + "\n\n".join(blocks)
        )
    except (Refused, KeyError, TypeError) as exc:
        return f"THORIN: refused — {exc}"


if __name__ == "__main__":
    server.run("stdio")
