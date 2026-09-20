# CLAUDE.md — knowledge/reports/

Generated reports and analyses written by R.A.D.A.G.A.S.T.: health/fitness
summaries, company/stock reports, sports-coach reviews, CV drafts, and any other
data-driven report. One report = one file. Radagast is the sole writer of this
folder.

## File naming

`YYYY-MM-DD_<slug>.md` — the date the report was generated, so reports sort
chronologically and re-runs on the same topic don't collide.
Slug = kebab-case, ≤40 chars, derived from the report title.
Examples: `2026-07-01_fitness-monthly-june.md`, `2026-07-01_cv-android-dev.md`.

## Frontmatter schema

Required (`brain/` schema): `date`, `source`, `privacy`, `tags`
Additional for reports:

```yaml
source: radagast
report_type: health | fitness | finance | cv | analysis | other
period: 2026-06                # the window the report covers, if applicable
data_sources: [fitness.db, brain/core/identity/profile.md]
tags: [reports, <report_type>, <period>]
title: "<Report title>"
```

## Body structure

```markdown
# <Report title>

<rendered tables / mermaid charts / sparklines>

## Trends & observations
<quantified deltas, named comparison window, flagged anomalies>

## Radagast's assessment
<his own conclusion or recommendation — always present, always distinct>

## Data used
<sources the report was built from>
```

## Privacy

Default `privacy` follows the sensitivity of the underlying data, not a blanket
`public`: health/fitness/finance-derived reports are `private`; a general-purpose
document like a CV draft may be `public`. When in doubt, mark `private`.
