# CLAUDE.md — knowledge/finance/analyses/

## Purpose
Investment analyses and pre-decision deliberations — a written trace of reasoning
before or during investment decisions.

## When to create a file
- Before investing in a new company (pre-investment analysis)
- Reviewing an existing position (periodic check-in)
- Evaluating whether to sell or increase exposure

## File naming
`YYYY-MM-DD_<TICKER>_<topic>.md`
- `2026-03-15_ABC_pre-investment.md`
- `2026-06-01_XYZ_rebalance-check.md`

## Privacy
Set `privacy: private` if the analysis reveals your position size or personal
financial decisions. Set `privacy: public` if it's pure company analysis with
no personal data.

## Frontmatter template
```yaml
date: <YYYY-MM-DDTHH:MM:SS>
source: manual
privacy: <public|private>
status: active
tags: [finance, analysis, <TICKER>]
title: "<TICKER> — <topic>"
```
