# CLAUDE.md — db/

## Purpose
SQLite databases for structured data queries. Each database is domain-specific.
Primary source for G.I.M.L.I. structured queries ("how much / when / count").

## Privacy level
**Mixed** — privacy is per database. See table below.

| Database | Privacy | Owner |
|---|---|---|
| `smeagol.db` | PRIVATE | S.M.E.A.G.O.L. |
| `fitness.db` | PRIVATE | `/daily` skill |

Add rows to this table as new databases are introduced.

## Access model — owners and G.I.M.L.I.

Every database has exactly one **owner**. Access splits by the *kind* of query:

| Kind | Who | Scope |
|---|---|---|
| **Operational** | the owner only | writes + fixed, pre-defined reads against *its own* database that serve its own function (e.g. "which reminders are due now", "does this id already exist") |
| **Analytical / ad hoc** | G.I.M.L.I. only | free-form SQL composed at runtime to answer a question — aggregations, trends, comparisons, cross-database queries |
| **Everything else** | nobody | no other agent, skill, or external system runs `sqlite3` against `db/` |

External systems (n8n, webhooks, other repos) never write here directly. They
report an event to the owner (via MCP, CLI, or HTTP), and the owner decides and
applies the change.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| Owner | ✅ | INSERT, idempotent upsert on its natural key (`INSERT OR REPLACE`), and UPDATE of state/lifecycle columns (e.g. `status`, `acked_at`). Never DELETE — append-only, rows change state instead of disappearing |
| User (manual) | ✅ | Schema changes must be additive |
| External systems (n8n, etc.) | ❌ | Notify the owner; the owner writes |
| Any other agent or skill | ❌ | No access — analytical reads go through G.I.M.L.I. |

## Schema rules
- Never DROP tables or columns
- Schema changes = additive only: `ALTER TABLE ADD COLUMN`, new tables
- Breaking changes require a new table + migration script in this folder

## Notes for Claude Code
G.I.M.L.I. queries `db/` for structured data, plus any external databases listed
in `GIMLI_EXTRA_DBS` (set in `.claude/gandalf.env`). The full registry is:
`brain/db/*.db` ∪ `GIMLI_EXTRA_DBS`. All sources are treated equally — none is
special-cased.

External databases reached through `GIMLI_EXTRA_DBS` are listed in this table for
privacy tracking only; they are **not** physically copied into `brain/db/`.

Always check the database's privacy level before including query results in API context.
`smeagol.db` is PRIVATE — results stay local.
`fitness.db` is PRIVATE — but see MVP exception below.

## MVP exception (Claude-API engine)

Documented in `Project-G.A.N.D.A.L.F./IMPLEMENTATION.md § "Privacy in the Claude-API MVP"`:
the Claude-API engine may receive PRIVATE content in its context window — consciously
accepted until Phase 2 (local models / Ollama). This applies to `fitness.db` and any
other PRIVATE database when the **user explicitly requests** an analysis in the session.

**Rule for G.I.M.L.I.:** when the user explicitly asks for a query against a PRIVATE
database, include the results in the response. Do NOT silently block the query — inform
the user of the privacy classification, then proceed under the MVP exception.
