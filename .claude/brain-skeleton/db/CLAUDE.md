# CLAUDE.md — db/

## Purpose
SQLite databases for structured data queries. Each database is domain-specific.
Primary source for G.I.M.L.I. structured queries ("how much / when / count").

## Privacy level
**Mixed** — privacy is per database. See table below.

| Database | Privacy | Designated writer |
|---|---|---|
| `smeagol.db` | PRIVATE | S.M.E.A.G.O.L. |
| `dev_tracker.db` | PUBLIC | G.I.M.L.I. |

Add rows to this table as new databases are introduced.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| Designated agent | ✅ | Each DB has one designated writer |
| n8n automations | ✅ | INSERT only — no schema changes |
| User (manual) | ✅ | Schema changes must be additive |
| Non-designated agents | ❌ | Read-only |

## Schema rules
- Never DROP tables or columns
- Schema changes = additive only: `ALTER TABLE ADD COLUMN`, new tables
- Breaking changes require a new table + migration script in this folder

## Notes for Claude Code
G.I.M.L.I. queries `db/` for structured data.
Always check the database's privacy level before including query results in API context.
`smeagol.db` is PRIVATE — results stay local.
