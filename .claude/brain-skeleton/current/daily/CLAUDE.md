# CLAUDE.md — current/daily/

## Purpose
Lightweight, append-only daily journal written by `/daily`. Captures a terse
digest of each day — not the routed facts themselves (those land in `core/`,
`backlog/`, `knowledge/`, etc. per `/daily`'s routing plan), just enough to
browse "what happened when" without re-reading the full processed note.

## Privacy level
**PRIVATE** — working memory, same as the rest of `current/`.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| `/daily` skill | ✅ | Only writer — append/merge, never duplicate a day |
| User (manual) | ✅ | Direct edits allowed, but prefer going through `/daily` |
| T.R.E.E.B.E.A.R.D. | ❌ | Not yet in scope — may consolidate old years later |
| Other CC agents | ❌ | Read-only |

## Allowed
- Appending a new day's section/row
- Merging new, non-duplicate content into the current day's existing
  section/row (idempotent re-run of `/daily` on the same date)

## Not allowed
- Per-day files — this folder holds rolling aggregates only
- Rewriting or deleting a previous day's section/row
- Duplicating a section/row for a date that already has one

## File format
Two files, both living documents (no timestamp in the name):
- `YYYY-MM.md` — monthly digest. One `## YYYY-MM-DD` section per day, 2–4 bullets.
- `YYYY.md` — yearly index. One table row per day (`| Date | Summary |`), up to
  365 rows.

Frontmatter on both: `source: daily`, `privacy: private`, `status: active`,
`tags: [daily, journal, <YYYY-MM or YYYY>]`. `date:` = first write, `updated:`
bumped on every write.

## Notes for Claude Code
This is an index/journal, not the canonical record — the canonical facts live
wherever `/daily` routed them. Use this folder to answer "what happened on/around
date X", then follow up in the routed targets for detail.
