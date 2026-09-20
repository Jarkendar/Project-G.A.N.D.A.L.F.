# CLAUDE.md — knowledge/finance/

## Purpose
Company financial data and investment analyses — separate from personal positions
(which live in `core/finance/finance.md`).

## Structure

```
knowledge/finance/
  <TICKER>/
    YYYY-QQ.md          ← quarterly report summary (e.g. 2025-Q1.md)
    YYYY-annual.md      ← annual report summary
  analyses/
    YYYY-MM-DD_<TICKER>_<topic>.md   ← investment analysis / pre-decision deliberation
```

## Privacy
Public by default — company financials are public data.
Set `privacy: private` per-file for analyses that reveal personal positions or decisions.

## File naming

| Type | Pattern | Example |
|---|---|---|
| Quarterly report | `YYYY-QQ.md` | `2024-Q4.md` |
| Annual report | `YYYY-annual.md` | `2024-annual.md` |
| Analysis | `YYYY-MM-DD_<TICKER>_<topic>.md` | `2026-03-15_ABC_pre-investment.md` |

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | — |
| Automated report ingestion skill | ✅ | Future — processes inbox → TICKER folder |
| Analysis skill | ✅ | Future — with user confirmation |
| Agents | ❌ | Read-only |

## What does NOT live here
- Personal positions, quantities, buy prices → `core/finance/finance.md`
- Credentials, API keys → nowhere in any repo

## Token efficiency note
Load per-file, not per-folder. One query = one report file. Never load all
`<TICKER>/` files unless explicitly doing a longitudinal analysis.
