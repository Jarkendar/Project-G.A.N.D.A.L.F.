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
agent: gloin
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
- Process tickers **sequentially**.
- You have no shell. Existing files are listed with `Glob`, US filings come
  from the `mcp__thorin__edgar_reports` tool, GPW pages from `WebFetch`, and
  the time for `date:` from `mcp__frodo__now` (call it once).

## Steps

For each ticker, fetch reports published **on or after** its `FIRST_BUY_DATE`.

First check what exists: `Glob` for `<brain>/knowledge/finance/<TICKER>/*.md`.

A report file that already exists (`YYYY-QQ.md` or `YYYY-annual.md`) is
**skipped**. Only fetch what is missing.

### US tickers — SEC EDGAR

**1. Call `mcp__thorin__edgar_reports(ticker, since)`** with the ticker and
its `FIRST_BUY_DATE`. It looks up the company, lists every 10-K and 10-Q filed
on or after that date and returns, per filing: the file name it belongs in
(`YYYY-QQ.md` for a 10-Q, by the quarter of its period end; `YYYY-annual.md`
for a 10-K), the form, period end, filing date, accession number and the key
figures — each with a short form (`$6.11B`), the exact value and the period it
covers. The company name is on the `company name:` line.

- `NO MATCH` → EDGAR does not list the ticker: reclassify it as `GPW`, note
  the reclassification for the output, and continue with the GPW flow.
- `refused` → log it as a failure for this ticker and go on to the next.
- A filing marked `NO FIGURES YET` gets **no file** — a later run picks it up.

**2. Skip a filing whose file already exists.**

**3. Write `<brain>/knowledge/finance/$TICKER/<file>`** for each of the rest.
Copy the figures as the tool gave them — the short form in the table, never
recomputed. `Total debt` is long-term debt plus short-term borrowings when the
tool gives both; one of them alone is written with its name
(`$874.00M (short-term borrowings only)`); neither → `n/a`. A figure the tool
marks as year to date keeps that mark: `$1.04B (YTD 2025-01-01 → 2025-06-30)`.

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
