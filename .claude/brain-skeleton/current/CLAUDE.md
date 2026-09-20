# CLAUDE.md — current/

## Purpose
Working memory: inbox for raw captures, Smeagol query logs, active project context.
Content is short-lived — T.R.E.E.B.E.A.R.D. consolidates and promotes to `knowledge/`
or `archive/` on a schedule.

## Privacy level
**PRIVATE** — treat all content as private unless explicitly moved to `knowledge/`.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Any subfolder |
| n8n automations | ✅ | `inbox/` only — see `inbox/CLAUDE.md` |
| S.M.E.A.G.O.L. | ✅ | `smeagol/` only — append-only |
| T.R.E.E.B.E.A.R.D. | ✅ | Reads all; writes to `context/`; moves from `inbox/` |
| Other CC agents | ❌ | Read-only |

## Subfolders
- `inbox/` — raw captures from automations and bookmarklets
- `smeagol/` — Gandalf query logs (append-only)
- `context/` — active project state

## Notes for Claude Code
Content here is transient. Do not treat it as canonical knowledge.
When promoting content to `knowledge/`, always re-evaluate the privacy level.
