# CLAUDE.md — current/context/

## Purpose
Active project state: what's in progress, current goals, open decisions.
One file per active project. T.R.E.E.B.E.A.R.D. archives files when status
changes to `archived`.

## Privacy level
**PRIVATE** — contains current work state, may include sensitive details.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Preferred — this is your working memory |
| T.R.E.E.B.E.A.R.D. | ✅ | Archiving completed projects, updating `status:` |
| n8n automations | ✅ | Trusted flows only; must set `source:` in frontmatter |
| Other CC agents | ❌ | Read-only |

## Allowed
- Creating and updating project context files
- Setting `status: archived` when done (T.R.E.E.B.E.A.R.D. then moves to `archive/`)

## Not allowed
- Deleting files — set `status: archived` instead
- More than one active file per project

## File format
Naming: `project-slug.md` (living documents — no timestamp)
Frontmatter: `status: draft | active | archived`

## Notes for Claude Code
Use `context/` to orient yourself on ongoing work.
When answering questions about active projects, prioritise this folder
over `knowledge/` — content here is more recent.
