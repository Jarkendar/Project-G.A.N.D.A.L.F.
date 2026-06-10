---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [health, body]
title: "Body parameters"
---

# Body parameters
> Living document — edit in place. `date` = last updated.
> Especially sensitive — populate only what you find useful.
> Medical state and habits live in `health.md`; this file is measurable parameters.

## Static
> Rarely changing.
- Date of birth:
- Height:
- Blood type:

## Current snapshot
> Latest value per metric. `as of` = date of the measurement, not the file edit.
- Weight:             (as of )
- Body fat %:         (as of )
- Resting heart rate: (as of )
- Blood pressure:     (as of )

## Measurement log
> Append-only time-series store. Add one row per measurement; never edit or delete
> past rows. Longitudinal queries ("trend", "average", "since") migrate to
> `db/` + G.I.M.L.I. later (storage-by-question-shape, principle #3). Until then,
> this table is the record.

| Date | Metric | Value | Unit | Notes |
|------|--------|-------|------|-------|

## Notes
