# CLAUDE.md — current/fitness/

## Purpose
Structured, append-only fitness journal populated by `/daily` via the Strava MCP
when a daily note mentions a sport activity. Captures objective workout stats
(distance, time, pace, heart rate) fetched live from Strava — this is not the
canonical record (Strava is), just a local rolling digest for "what did I train,
when" plus month/year totals, without re-querying the API every time.

## Privacy level
**PRIVATE** — working memory, same as the rest of `current/`.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| `/daily` skill (via Strava MCP) | ✅ | Only writer — append/merge keyed by Strava activity ID, never duplicate |
| User (manual) | ✅ | Direct edits allowed, but prefer going through `/daily` |
| T.R.E.E.B.E.A.R.D. | ❌ | Not yet in scope — may consolidate old years later |
| Other CC agents | ❌ | Read-only |

## Allowed
- Appending a new activity's entry (and updating month totals) to the current
  month file
- Updating an existing activity's entry in place if `/daily` re-fetches the same
  Strava activity ID (e.g. corrected after the fact on Strava)
- Updating the current month's row in the yearly index as new activities arrive

## Not allowed
- Per-activity files — this folder holds rolling monthly/yearly aggregates only
- Duplicating an entry for a Strava activity ID that's already logged
- Treating this folder as the canonical activity record — Strava itself is

## File format
Two files, both living documents (no timestamp in the name):
- `YYYY-MM.md` — monthly digest. A "Month totals" block plus one section per
  activity, keyed by Strava activity ID.
- `YYYY.md` — yearly index. One table row per month, aggregated totals.

Frontmatter on both: `source: daily`, `privacy: private`, `status: active`,
`tags: [fitness, strava, journal, <YYYY-MM or YYYY>]`. `date:` = first write,
`updated:` bumped on every write.

## Notes for Claude Code
Numbers here are fetched from Strava at write time — if an activity is later
corrected on Strava, this digest goes stale until `/daily` re-fetches that date.
Treat as a fast local index, not ground truth; Strava itself is authoritative.
