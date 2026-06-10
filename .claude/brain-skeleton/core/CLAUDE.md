# CLAUDE.md — core/

## Purpose
Permanent personal facts: identity, health, finance. Things that rarely change
and are deeply private.

## Privacy level
**PRIVATE** — contents never leave this machine. Never pass to external APIs.
Never include in Claude API context window, even in summarised form.

MVP exception: private content may enter the Claude API context window in the MVP.
See IMPLEMENTATION.md § "Privacy in the Claude-API MVP". Tightened in Phase 2.

## Document model
`core/` uses **living documents** edited in place — not the timestamped-file
append-only model used by `inbox/` or `conversations/`.

| Convention | Value |
|---|---|
| File naming | `slug.md` (e.g. `profile.md`, `goals.md`) |
| `date:` field | Last-updated timestamp, bumped on every edit |
| Updates | Edit in place; preserve all other content verbatim |
| Major revisions (opt-in) | Archive pre-edit copy to `archive/`; set `supersedes:` in new version |

Supersession (`superseded_by:`) is written by T.R.E.E.B.E.A.R.D. only.

## Living documents

| File | Purpose |
|---|---|
| `identity/profile.md` | Who I am — name, location, role, languages, background, preferences |
| `identity/goals.md` | Goals and horizons — long-term, current quarter, someday/maybe |
| `identity/contacts.md` | People, relationships, context |
| `health/health.md` | Medical state — conditions, allergies, meds, vaccinations, habits |
| `health/body.md`   | Measurable body parameters — static stats + measurement log |
| `finance/finance.md` | Financial overview and notes |

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Any file; frontmatter required |
| `/update-core` skill | ✅ | Only with explicit user confirmation at each write |
| T.R.E.E.B.E.A.R.D. | ✅ | Supersession only — no new facts |
| n8n automations | ❌ | Not allowed |
| Other CC agents | ❌ | Read access only |

## Allowed
- Editing living documents in place via the `/update-core` skill
- Creating new living documents from templates (via `/update-core`)
- Optional archiving of major revisions to `archive/` with `supersedes:`

## Not allowed
- Deleting any file
- Writing without frontmatter
- Any automation writing here — manual / `/update-core` only

## Required frontmatter (all core/ files)
```yaml
date: <last-updated, ISO 8601>
source: manual
privacy: private
status: active
tags: [<at least one tag>]
```

## Notes for Claude Code
You are in a PRIVATE scope. Do not read files here and include their content
in any prompt sent to an external API. Local model access only (Phase 2).
In MVP: read locally, do not relay content to Claude API.
To add or update facts, use the `/update-core` skill.
