---
name: fetch-finance-reports
description: >-
  Forked fetch-and-write helper for /ingest-finance — for a list of held
  tickers, pulls the missing 10-K/10-Q (SEC EDGAR) and GPW report summaries
  published since the first buy and writes them to
  knowledge/finance/<TICKER>/. Returns only counts, reclassifications and
  failures. Public company data only. Called by ingest-finance step 5, not
  meant to be invoked on its own.
context: fork
model: sonnet
user-invocable: false
---

# fetch-finance-reports

The report-fetching half of `/ingest-finance`, split out because EDGAR
`companyfacts` JSON and broker pages are large and would otherwise flood the
caller's context. You fetch and write the report files; the caller keeps the
portfolio parsing and the privacy-gated write to `finance.md`.

You get **no conversation history** — everything you need is in the arguments.

## Input

`$ARGUMENTS`:

```
brain: <absolute path to brain/>
<TICKER> <US|GPW> <FIRST_BUY_DATE YYYY-MM-DD>
<TICKER> <US|GPW> <FIRST_BUY_DATE>
...
```

ETFs and `UNKNOWN` tickers are never passed. If `brain` is missing or does not
exist, or a line is malformed, stop and say so.

## Boundaries

- **Write only** to `<brain>/knowledge/finance/<TICKER>/`. Never read or write
  `core/`, `current/`, `_meta/` or any other folder — in particular not
  `core/finance/finance.md`; the caller owns it.
- The only data that leaves the machine is the ticker and the first-buy date
  (as a search window) in EDGAR / broker queries.
- Never overwrite an existing report file.
- Process tickers **sequentially**. SEC EDGAR allows 10 req/s; with more than 5
  US tickers pause ~200 ms between EDGAR requests.

## Steps

For each ticker, fetch reports published **on or after** its `FIRST_BUY_DATE`.

First check what exists:

```bash
ls "<brain>/knowledge/finance/$TICKER/" 2>/dev/null
```

A report file that already exists (`YYYY-QQ.md` or `YYYY-annual.md`) is
**skipped**. Only fetch what is missing.

### US tickers — SEC EDGAR

**1. Look up the CIK.** Query
`https://efts.sec.gov/LATEST/search-index?q=%22<TICKER>%22&dateRange=custom&startdt=<FIRST_BUY_DATE>&forms=10-K,10-Q`
or
`https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=<TICKER>&type=10-K&dateb=&owner=include&count=10&search_text=&action=getcompany`.
Extract the CIK zero-padded to 10 digits (`$CIK`). No CIK found → reclassify
the ticker as `GPW`, note the reclassification for the output, and continue
with the GPW flow.

**2. Fetch the submissions list:** `https://data.sec.gov/submissions/CIK<$CIK>.json`.
From `filings.recent` take every 10-K and 10-Q with `filingDate >=
FIRST_BUY_DATE`; keep `form`, `filingDate`, `reportDate` (period end),
`accessionNumber`.

**3. Name the file from `reportDate`:**
- 10-Q → `YYYY-QQ.md`, QQ = `Q1` (Jan–Mar), `Q2` (Apr–Jun), `Q3` (Jul–Sep),
  `Q4` (Oct–Dec) by quarter-end month.
- 10-K → `YYYY-annual.md`.

Skip the filing if that file already exists.

**4. Fetch key financials:** `https://data.sec.gov/api/xbrl/companyfacts/CIK<$CIK>.json`.
For the entry whose `end` equals `reportDate` and whose `form` matches (latest
`filed` if duplicated), `USD` unit:
- Revenue: `us-gaap/Revenues` or
  `us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax`
- Net income: `us-gaap/NetIncomeLoss`
- EPS: `us-gaap/EarningsPerShareBasic`
- Total assets: `us-gaap/Assets`
- Total debt: `us-gaap/LongTermDebt` + `us-gaap/ShortTermBorrowings`
- Operating cash flow: `us-gaap/NetCashProvidedByUsedInOperatingActivities`

`entityName` from the JSON root is the company name. A metric missing from
XBRL is `n/a`.

**5. Write `<brain>/knowledge/finance/$TICKER/<key>.md`:**

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>   ← now
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

### GPW tickers — web fetch

**1. Find the report list.** Try in order:
1. `https://www.biznesradar.pl/raporty-finansowe/<TICKER>/` — table of
   quarterly / annual reports with dates.
2. `https://www.bankier.pl/gielda/notowania/<TICKER>/wyniki-finansowe`.

List the reports (period, link) published on or after `FIRST_BUY_DATE`.

**2. Fetch each missing report's summary / table page** — not the PDF. Extract
period, revenue, net income, EPS, total assets, operating cash flow (whatever is
there) and the source URL. If only a PDF link exists, record `source_url` and
the note "Full data available in PDF — manual extraction required." Do not
attempt PDF parsing.

**3. Write the file** with the template above, but `source: web-fetch` and
`source_url: <url>`. Partial extraction: fill what is available, `n/a` for the
rest, and add under `## Notes`: "Partial data — some metrics not available from
web source."

**Backfill is best-effort.** If a period is not available at all, write a stub:

```markdown
---
date: <now>
source: stub
privacy: public
status: stub
tags: [finance, <TICKER>]
title: "<TICKER> — <period> (data unavailable)"
---
_Report data not available from web sources for this period. Manual entry required._
```

### Failures

A fetch error (network, 404, rate limit) is logged as
`<TICKER> (<source>): <error>`; carry on with the next ticker. Never abort the
whole run on one ticker.

## Output

Return exactly this, nothing before or after. No file contents, no raw JSON:

```
written: <n>
skipped (already existed): <n>
stubs: <n>
reclassified: <TICKER US→GPW>, ...   | none
failures:
  <TICKER> (<source>): <error>       | none
```
