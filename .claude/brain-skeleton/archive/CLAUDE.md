# CLAUDE.md — archive/

## Purpose
Permanent record of superseded entries. Every file replaced via the supersession
chain ends up here. The archive is immutable — nothing is ever deleted.

## Privacy level
**Mixed** — mirrors the privacy of the original file.
Check each file's `privacy:` field before including content in API context.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| T.R.E.E.B.E.A.R.D. | ✅ | Sole writer — moves superseded files here |
| User (manual) | ❌ | Use T.R.E.E.B.E.A.R.D. for archiving — do not write directly |
| Any other source | ❌ | Not allowed |

## Allowed
- Reading any file for historical context
- Following `superseded_by` chain to find current version

## Not allowed
- Deleting files — ever
- Modifying files — ever
- Writing new files directly (T.R.E.E.B.E.A.R.D. only)

## Notes for Claude Code
Read-only for all agents except T.R.E.E.B.E.A.R.D.
Default queries exclude `archive/`. Access history only when explicitly requested.
