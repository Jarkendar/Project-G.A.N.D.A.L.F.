# ingest-finance

Process a myFund portfolio export from `brain/current/inbox/` into the finance
knowledge base. Updates portfolio positions in `core/finance/finance.md` and fetches
company reports for each held ticker into `knowledge/finance/<TICKER>/`.

## When to use

- After placing a myFund XML or CSV export in `brain/current/inbox/` (monthly cycle).
- To process a specific file: `/ingest-finance <filename>`.
- To process all finance exports in the inbox: `/ingest-finance`.

---

## Manual step before running

Export the portfolio from myFund:
**menu → Zarządzanie → Twoje portfele → Eksportuj wszystkie portfele**

Save the resulting XML file(s) into `brain/current/inbox/` using the naming
convention: `YYYY-MM-DD_myfund_<portfel>.xml` (e.g. `2026-06-12_myfund_ike.xml`).

One export per brokerage account is the recommended approach — myFund exports
each portfolio separately.

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.
Resolve relative paths from the project root. Call it `$BRAIN`.

If the file does not exist or `BRAIN_PATH` is empty:
- Tell the user to copy `.claude/gandalf.env.example` and set `BRAIN_PATH`. Stop.

Verify `$BRAIN/core/finance/finance.md` exists. If not: tell the user to run
`/init-brain` first. Stop.

### 2. Locate the export file

Inbox: `$BRAIN/current/inbox/`

If an argument was passed (e.g. `/ingest-finance 2026-06-12_myfund_ike.xml`):
- Target = that single file. If not found: report error and stop.

Otherwise:
- Target = all `.xml` and `.md` files in inbox whose names contain `myfund` or
  `portfel` (case-insensitive), excluding the `_processed/` subfolder.
- If none found: report "Nothing to do — no myFund export found in inbox." and stop.
- If multiple files found: list them and ask the user which one(s) to process.

**Accepted formats:** `.xml` (raw myFund export) and `.md` (pre-converted readable
export — see step 2a). Both carry the same position data; the skill auto-detects
the format.

### 2a. Convert XML → MD (if input is XML)

If the target file is `.xml`, convert it to a human-readable `.md` before parsing.
This makes the export auditable and browsable without tools.

For each `.xml` file, produce `YYYY-MM-DD_myfund_<portfel>.md` alongside it in
`_processed/` with this structure:

```markdown
---
date: <export date>T<time>
source: myfund-export
privacy: private
status: active
tags: [finance, myFund, <portfel>]
title: "myFund <Portfel> — eksport <YYYY-MM-DD>"
---

# myFund <Portfel> — eksport <YYYY-MM-DD>

## Otwarte pozycje (<n>)

| Ticker | Ilość | Śr. cena zakupu | Waluta | First buy |
|---|---|---|---|---|
| <TICKER> | <qty> | <avg_buy> | <waluta> | <first_buy> |

## Zamknięte pozycje (<n>)

| Ticker | Śr. cena zakupu | Waluta | First buy | Last sell |
|---|---|---|---|---|

## Historia transakcji

| Data | Ticker | Typ | Ilość | Cena |
|---|---|---|---|---|
```

The MD file is written to `$BRAIN/current/inbox/_processed/` (same folder where
the XML lands after processing). If the MD already exists, overwrite it.

If the input is already `.md` (user ran the conversion manually), skip this step.

### 3. Parse the export

Read the file. The myFund XML format uses `<operacje>` elements — one per transaction.
Key fields per `<operacje>`:

| XML field | Meaning |
|---|---|
| `TICKER` | Instrument identifier |
| `LICZBAJEDNOSTEK` | Transaction quantity — **already signed**: positive = buy, negative = sell |
| `CENA` | Price per unit (in `WALUTA`) |
| `WALUTA` | Currency of the transaction |
| `DATA` | Transaction date (`YYYY-MM-DD`) |
| `TYP` | Transaction type: `Kupno`, `Sprzedaz`, `Konwersja Akcji nabycie`, etc. |

**Parsing logic — net position per ticker:**

```
for each operacje where TICKER is non-empty:
    qty += LICZBAJEDNOSTEK          # signed: always add (sells are already negative)
    if LICZBAJEDNOSTEK > 0:         # buy
        buy_cost += LICZBAJEDNOSTEK * CENA
        buy_qty  += LICZBAJEDNOSTEK
        first_buy = min(first_buy, DATA)
    else:                           # sell / conversion out
        last_sell = max(last_sell, DATA)

open positions:   qty >  0.001
closed positions: qty <= 0.001
```

Only open positions are written to `finance.md` and trigger report fetching.
Closed positions are noted in the final report but not stored.

Each open position must yield:

| Field | Description |
|---|---|
| `TICKER` | Instrument identifier |
| `QTY` | Net quantity held |
| `AVG_BUY` | `buy_cost / buy_qty` |
| `WALUTA` | Currency |
| `FIRST_BUY_DATE` | Date of first buy (`YYYY-MM-DD`) |
| `ASSET_CLASS` | One of: `ETF`, `US`, `GPW` — see classification rules below |

**Classification rules (step 3a):**

Classify each ticker into `ETF`, `US`, or `GPW`:

1. **ETF** (skip report fetching):
   - Ticker ends in `ETF`, `UCITS`, or is a known ETF identifier (e.g. `VWCE`,
     `EUNL`, `CSPX`, `SWRD`, `AGGH`).
   - Name in the export contains "ETF", "UCITS", or "fund".
2. **US** (use SEC EDGAR):
   - Ticker is 1–5 uppercase Latin letters with no `.` suffix.
   - Exchange in the export is `NYSE`, `NASDAQ`, `NYSE ARCA`, `BATS`, or similar
     US exchange.
   - When unsure, attempt EDGAR lookup (step 5a); fall back to `GPW` if EDGAR
     returns no match.
3. **GPW** (use WebFetch):
   - Everything else — Polish tickers, tickers with `.` suffix (e.g. `.PL`),
     or tickers whose EDGAR lookup returned no match.

If a ticker cannot be confidently classified after EDGAR attempt, report it as
`UNKNOWN` and skip report fetching for it. List unknowns in the final report.

**If the file format is unrecognised or yields zero rows:**
- Show the first 20 lines of the file to the user.
- Ask: "Could not auto-parse this file. What format is this — XML / CSV / other?"
- Accept a manual paste of the position table (ticker, qty, avg buy, first buy date)
  as a fallback, then continue.

### 4. Show parse summary and confirm

Before touching any files, show the user what was extracted:

```
── Parsed positions ────────────────────────────────────
Source: <filename>
─────────────────────────────────────────────────────────
TICKER    CLASS   QTY     AVG_BUY       FIRST_BUY
VWCE      ETF     12      €94.30        2023-04-15
CDR       GPW     5       122.40 PLN    2024-01-08
REALTY    US      20      $55.12        2023-11-20
…
─────────────────────────────────────────────────────────
<n> positions total  |  <n> US  |  <n> GPW  |  <n> ETF
─────────────────────────────────────────────────────────
Proceed? [y / n / edit]
```

- **y** → continue to step 5.
- **n** → stop. Nothing is written.
- **edit** → let the user correct ticker classifications or remove rows, then
  re-show and ask again.

### 5. Fetch company reports (per non-ETF ticker)

For each ticker with `ASSET_CLASS = US` or `GPW`, fetch reports published
**on or after `FIRST_BUY_DATE`**. Skip ETFs entirely — they get no report files.

Check existing reports first:

```bash
ls "$BRAIN/knowledge/finance/$TICKER/" 2>/dev/null
```

A report file that already exists (`YYYY-QQ.md` or `YYYY-annual.md`) is **skipped**
— do not overwrite. Only fetch reports missing from the folder.

#### 5a. US tickers — SEC EDGAR

**Step 1: Look up CIK**

```
https://efts.sec.gov/LATEST/search-index?q=%22<TICKER>%22&dateRange=custom&startdt=<FIRST_BUY_DATE>&forms=10-K,10-Q
```

Or use the company search endpoint:

```
https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=<TICKER>&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany
```

Extract `CIK` (zero-padded to 10 digits). Call it `$CIK`.

If no CIK found: reclassify ticker as `GPW` and proceed to step 5b.

**Step 2: Fetch submissions list**

```
https://data.sec.gov/submissions/CIK<$CIK>.json
```

Parse the `filings.recent` object. Extract all 10-K and 10-Q filings with
`filingDate >= FIRST_BUY_DATE`. For each filing collect:
- `form` (10-K or 10-Q)
- `filingDate`
- `reportDate` (the period end date)
- `accessionNumber`

**Step 3: Determine report filename**

Map `reportDate` to the filename key:
- 10-Q → `YYYY-QQ.md` where QQ = `Q1` (Jan–Mar), `Q2` (Apr–Jun), `Q3` (Jul–Sep),
  `Q4` (Oct–Dec) based on the quarter end month.
- 10-K → `YYYY-annual.md`

If a file with this name already exists in `$BRAIN/knowledge/finance/$TICKER/`:
skip it.

**Step 4: Fetch key financials from CompanyFacts**

```
https://data.sec.gov/api/xbrl/companyfacts/CIK<$CIK>.json
```

From the JSON, extract for the matching period (using `end` date matching
`reportDate`):
- Revenue: `us-gaap/Revenues` or `us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax`
- Net income: `us-gaap/NetIncomeLoss`
- EPS: `us-gaap/EarningsPerShareBasic`
- Total assets: `us-gaap/Assets`
- Total debt: `us-gaap/LongTermDebt` + `us-gaap/ShortTermBorrowings`
- Operating cash flow: `us-gaap/NetCashProvidedByUsedInOperatingActivities`

Use the `USD` unit entries. Match the entry where `form` matches and `end` date
matches `reportDate`. Take the most recent `filed` entry if duplicates exist.

Include `entityName` from the JSON root as the company name.

**Step 5: Compose summary file**

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>   ← ingest datetime
source: sec-edgar
privacy: public
status: active
tags: [finance, <TICKER>, <10-K or 10-Q>, <YYYY>]
title: "<COMPANY_NAME> — <form> <period>"
---

# <COMPANY_NAME> — <form> period ending <reportDate>

> Source: SEC EDGAR filing <accessionNumber>, filed <filingDate>.

## Key financials

| Metric | Value |
|---|---|
| Revenue | <value> |
| Net income | <value> |
| EPS (basic) | <value> |
| Total assets | <value> |
| Total debt | <value> |
| Operating cash flow | <value> |

## Notes

_No notes yet._
```

If a metric is not available in XBRL data, write `n/a`.

#### 5b. GPW tickers — WebFetch

**Step 1: Locate IR page**

Attempt to fetch the investor relations / reports page for the company. Try in order:
1. `https://www.biznesradar.pl/raporty-finansowe/<TICKER>/` — look for a table of
   quarterly/annual reports with dates.
2. `https://www.bankier.pl/gielda/notowania/<TICKER>/wyniki-finansowe` — similar.

Extract a list of available reports (period, link) published on or after
`FIRST_BUY_DATE`.

**Step 2: Fetch filing page**

For each available report not yet present in `$BRAIN/knowledge/finance/$TICKER/`:
fetch its summary/table page (not the raw PDF) and extract:
- Period (quarter or annual)
- Revenue, net income, EPS, total assets, operating cash flow (whatever is available)
- Source URL

If only a PDF link is available and no HTML table: record `source_url` and note
"Full data available in PDF — manual extraction required." Do not attempt PDF parsing.

**Step 3: Compose summary file**

Same template as step 5a, but `source: web-fetch` and `source_url: <url>`.

If extraction partially failed: fill available fields; write `n/a` for missing ones;
add a `## Notes` entry: "Partial data — some metrics not available from web source."

#### 5c. Handle fetch failures gracefully

If a fetch returns an error (network, 404, rate-limit):
- Log the failure: `"⚠️ <TICKER> (<source>): <error>"`
- Continue with the remaining tickers.
- Report all failures at the end (step 8).

Do not abort the entire ingest on a single ticker failure.

### 6. Update finance.md — Portfolio positions

Read `$BRAIN/core/finance/finance.md`.

Locate the `## Portfolio positions` section. The section contains a `>` comment
line and then either an empty body or existing entries.

**For each position from the parsed export:**

If the ticker already has a line in the section:
- Update `quantity` and `avg_buy_price` in place (these change with new purchases).
- Preserve any existing `notes` on the line.

If the ticker is new:
- Append a new line at the end of the section.

Format per entry (one bullet per ticker):
```
- **<TICKER>** (<ASSET_CLASS>) — <QTY> units @ <AVG_BUY> avg | first buy: <FIRST_BUY_DATE>
```

Example:
```
- **VWCE** (ETF) — 12 units @ €94.30 avg | first buy: 2023-04-15
- **CDR** (GPW) — 5 units @ 122.40 PLN avg | first buy: 2024-01-08
- **REALTY** (US) — 20 units @ $55.12 avg | first buy: 2023-11-20
```

Do **not** remove lines for tickers that are no longer in the export (they may have
been sold — mark them instead):
- If a ticker was in the file but is absent from the new export, append
  ` | ~~sold or closed~~` to that line (do not delete the line; ownership history
  is preserved). Ask the user to confirm this interpretation first if any ticker
  disappears.

**Privacy gate:** before writing `finance.md`, show the user:

```
── Proposed change to finance.md ────────────────────────
File:    <$BRAIN/core/finance/finance.md>
Mode:    edit in place (Portfolio positions section)
Privacy: PRIVATE ⚠️  (stays on this machine; MVP exception: Claude API context)
─────────────────────────────────────────────────────────
Change summary:
  <n> positions updated, <n> new positions added
  <list of changed lines>
─────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

On `y`: write. Update `date:` in frontmatter to current ISO 8601 datetime.
On `n`: skip finance.md update (report files are unaffected).
On `edit`: let the user adjust, then re-confirm.

### 7. Write report files

For each report summary composed in step 5 (and not yet on disk):

1. Create `$BRAIN/knowledge/finance/$TICKER/` if it does not exist.
2. Write the summary file as `$BRAIN/knowledge/finance/$TICKER/<key>.md`
   where `<key>` is `YYYY-QQ` or `YYYY-annual`.

No privacy gate per file — these are public company data (`privacy: public`).
Write all at once after the finance.md gate.

### 8. Report

```
── ingest-finance complete ─────────────────────────────
✅ Positions updated: <n> in finance.md
✅ Report files written: <n>
⏭️  Report files skipped (already existed): <n>
⚠️  Fetch failures: <n>
❌ Unknown tickers (manual review needed): <n>
─────────────────────────────────────────────────────────
Failures / unknowns:
  <TICKER>: <reason>
─────────────────────────────────────────────────────────
Next step: run /ingest-finance again after resolving failures, or
add missing reports manually to knowledge/finance/<TICKER>/
```

### 9. Move processed file

After a successful run (even partial), move the source file out of inbox:

```bash
mkdir -p "$BRAIN/current/inbox/_processed"
mv "$BRAIN/current/inbox/<filename>" "$BRAIN/current/inbox/_processed/<filename>"
```

---

## Notes

- **ETFs: positions only.** ETFs are recorded in `finance.md` (ticker, qty, avg
  buy) but no report files are created for them. They do not have earnings reports
  in the traditional sense.
- **Incremental by design.** Already-present report files are never overwritten.
  Re-running the skill is safe — only missing reports are fetched.
- **SEC EDGAR rate limit:** 10 req/s. The skill processes tickers sequentially, not
  in parallel, to respect this limit. Add a 200ms pause between EDGAR requests if
  the portfolio has more than 5 US tickers.
- **GPW backfill is best-effort.** Historical reports may not be available through
  web sources. If a period is missing, write a stub file:
  ```markdown
  ---
  date: <ingest datetime>
  source: stub
  privacy: public
  status: stub
  tags: [finance, <TICKER>]
  title: "<TICKER> — <period> (data unavailable)"
  ---
  _Report data not available from web sources for this period. Manual entry required._
  ```
- **Sold positions.** The skill does not delete positions from `finance.md`. A
  ticker absent from the export is flagged as potentially sold — the user confirms
  before the line is annotated.
- **finance.md is PRIVATE.** Every write to it goes through the privacy gate (step 6).
  Report files in `knowledge/finance/` are public by default.
- **Does not touch `_meta/`.** `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory.
- **Saldo Inteligo:** not handled by this skill. Add it manually to the
  `## Accounts & institutions` section via `/update-core` or `/interview`.
- **PPK / Santander-Erste:** not in myFund export scope. Add manually if needed.
