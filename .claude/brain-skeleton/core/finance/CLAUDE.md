# CLAUDE.md — core/finance/

## Purpose
Personal financial data: accounts, owned positions, budget, investment principles.
Highest-sensitivity subfolder in `core/`.

## Privacy level
**PRIVATE** — never pass to external APIs.
MVP exception: may enter Claude API context window — see IMPLEMENTATION.md.

## What lives here

| File | Content |
|---|---|
| `finance.md` | Accounts, portfolio positions (ticker + quantity + avg buy price), budget, investment strategy |
| `majatek-netto.md` | Roczny bilans majątku netto — aktywa (konta, ruchomości, nieruchomości) minus pasywa (kredyty) |

## What does NOT live here
- API keys, passwords, tokens — **never in any repo**
- Raw brokerage exports — store processed summaries only
- Company report summaries → `knowledge/finance/<TICKER>/`
- Investment analyses → `knowledge/finance/analyses/`

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Any content |
| `/update-core` skill | ✅ | With explicit user confirmation |
| `/interview` skill | ✅ | With explicit user confirmation |
| Automated flows | ❌ | Not allowed |
| Agents | ❌ | Read-only |
