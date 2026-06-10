# CLAUDE.md — brain/

## Purpose
Personal knowledge repository for G.A.N.D.A.L.F. Contains structured and
unstructured data across privacy levels. This repo is data-only — no executable code.

## Repository structure

| Folder | Privacy | Purpose |
|---|---|---|
| `core/` | PRIVATE | Permanent personal facts — never to external APIs |
| `current/` | PRIVATE | Working memory — inbox, logs, active context |
| `knowledge/` | PUBLIC | Curated knowledge base — may reach Claude API |
| `archive/` | mixed | Superseded entries — follow superseded_by chain |
| `db/` | mixed | SQLite databases — privacy per database |
| `_meta/` | PRIVATE | Manifest, queue, schema — structural metadata |

## Global rules
- Append-only: never delete files. Use supersession (`superseded_by`) instead.
- All markdown files require frontmatter. See `_meta/schema.md` for the spec.
- Privacy is enforced per folder first, then per file. A file in `core/` is always
  PRIVATE regardless of its own `privacy:` field.

## For Claude Code agents
- Always check the CLAUDE.md of the specific subfolder you are operating in.
- Never read `core/` or `current/` content and pass it to an external API.
- T.R.E.E.B.E.A.R.D. is the only agent authorised to write `superseded_by` fields.
- When spawned in a subfolder, your working scope is that subfolder only.
