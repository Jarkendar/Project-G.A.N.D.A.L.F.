# CLAUDE.md — current/inbox/

## Purpose
Landing zone for all raw external input: n8n outputs, bookmarklet exports,
unprocessed captures. Files wait here for T.R.E.E.B.E.A.R.D. to process them
via `_meta/queue.jsonl`.

## Privacy level
**PRIVATE** — treat as private until explicitly reclassified on move.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Valid frontmatter required (pre-commit hook validates) |
| n8n automations | ✅ | Any flow — frontmatter required |
| Bookmarklets | ✅ | Chat/page exports |
| T.R.E.E.B.E.A.R.D. | ❌ | Reads only — does not write here |
| Other agents | ❌ | No writes |

## Allowed
- Adding new files with complete frontmatter
- Any content type: articles, chat exports, notes, raw data

## Not allowed
- Processing or editing files in place — move them out instead
- Deleting files — T.R.E.E.B.E.A.R.D. moves them, never deletes
- Writing without frontmatter — pre-commit hook will reject

## File format
Naming: `YYYY-MM-DDTHH-MM-SS_source_slug.md`
Required frontmatter: `date`, `source`, `privacy`, `tags`
After adding a file: append an entry to `_meta/queue.jsonl` with `status: pending`

## Notes for Claude Code
This is a staging area only. Do not synthesise or act on content here.
Report inbox size and pending queue count when asked; do not process without
explicit instruction or T.R.E.E.B.E.A.R.D. trigger.
