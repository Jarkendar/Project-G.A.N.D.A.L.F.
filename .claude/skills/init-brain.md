# init-brain

Initialize or validate the `brain/` knowledge repository for G.A.N.D.A.L.F.

## When to use

- First-time setup: `brain/` does not exist yet
- After cloning this repo on a new machine
- Validating that an existing `brain/` has the correct structure
- Recovering missing `CLAUDE.md` or `_meta/` files

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist:
- Tell the user: "`.claude/gandalf.env` not found. Copy `.claude/gandalf.env.example`
  to `.claude/gandalf.env` and set `BRAIN_PATH` to the path of your brain/ repo."
- Stop.

If `BRAIN_PATH` is not set or empty:
- Tell the user to set `BRAIN_PATH` in `.claude/gandalf.env`.
- Stop.

Resolve the path (expand `~`, resolve relative paths from the project root).
Call it `$BRAIN`.

### 2. Check existence

If `$BRAIN` exists:
- Run **Validation mode** (Step 4).

If `$BRAIN` does not exist:
- Tell the user the resolved path and ask: "brain/ not found at `$BRAIN`. Create scaffold?"
- On confirmation: run **Creation mode** (Step 3).
- On refusal: stop.

### 3. Creation mode

Create the following directory structure under `$BRAIN`:

```
$BRAIN/
  _meta/
  core/
    identity/
    health/
    finance/
  current/
    inbox/
    smeagol/
    context/
  knowledge/
    tech/
    projects/
    notes/
  conversations/
  archive/
  db/
```

Then write each file listed in the **File templates** section below.

After creation, print a summary: list every file created.

### 4. Validation mode

Check that the following paths exist. For each missing item, offer to create it.

Directories:
- `$BRAIN/_meta/`
- `$BRAIN/core/` and subdirs: `identity/`, `health/`, `finance/`
- `$BRAIN/current/` and subdirs: `inbox/`, `smeagol/`, `context/`
- `$BRAIN/knowledge/` and subdirs: `tech/`, `projects/`, `notes/`
- `$BRAIN/conversations/`
- `$BRAIN/archive/`
- `$BRAIN/db/`

Files:
- `$BRAIN/CLAUDE.md`
- `$BRAIN/_meta/schema.md`
- `$BRAIN/_meta/queue.jsonl`
- `$BRAIN/_meta/manifest.json`
- `$BRAIN/core/CLAUDE.md`
- `$BRAIN/core/identity/profile.md`
- `$BRAIN/core/identity/goals.md`
- `$BRAIN/core/identity/contacts.md`
- `$BRAIN/core/health/health.md`
- `$BRAIN/core/health/body.md`
- `$BRAIN/core/finance/finance.md`
- `$BRAIN/current/CLAUDE.md`
- `$BRAIN/current/inbox/CLAUDE.md`
- `$BRAIN/current/smeagol/CLAUDE.md`
- `$BRAIN/current/context/CLAUDE.md`
- `$BRAIN/knowledge/CLAUDE.md`
- `$BRAIN/conversations/CLAUDE.md`
- `$BRAIN/archive/CLAUDE.md`
- `$BRAIN/db/CLAUDE.md`

Print validation report: ✅ present / ❌ missing for each item.

---

## File templates

Write each file exactly as specified below. Do not add or remove content.

---

### `$BRAIN/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/_meta/schema.md`

````markdown
# schema.md — brain/ frontmatter specification

All markdown files in `brain/` must include YAML frontmatter. This document
is the canonical specification.

## Required fields

```yaml
date: 2026-06-08T14:30:00    # ISO 8601, creation datetime
source: manual               # who/what created this file
                             # values: manual | n8n/<flow-name> | bookmarklet | treebeard
privacy: public              # privacy level — values: private | public
tags: [tag1, tag2]           # list, at least one tag required
```

## Optional fields

```yaml
title: "Human readable title"           # when different from H1 heading
supersedes: path/to/older.md            # this file replaces an older entry
superseded_by: path/to/newer.md         # set by T.R.E.E.B.E.A.R.D. — do not set manually
processed_at: 2026-06-08T16:00:00       # when moved out of inbox (set by T.R.E.E.B.E.A.R.D.)
status: active                          # lifecycle: draft | active | archived
assistant: claude                       # conversations/ only — detected assistant (claude|gemini|unknown)
content_hash: sha256:<hex>              # conversations/ only — SHA-256 of raw transcript for dedup
```

## Naming convention

Files created by automations or agents:
```
YYYY-MM-DDTHH-MM-SS_source_slug.md
```
Example: `2026-06-08T14-30-00_n8n_python-article.md`

Living documents (updated in place, no timestamp):
```
slug.md
```
Example: `project-gandalf.md` in `current/context/`

## Supersession chain

When a fact changes, create a new file with `supersedes:` pointing to the old one.
T.R.E.E.B.E.A.R.D. then sets `superseded_by:` in the old file.

Default retrieval: skip files where `superseded_by` is set.
Historical retrieval: follow the `supersedes` chain backward.

Chain direction:
- newest → (supersedes) → ... → oldest
- oldest → (superseded_by) → ... → newest

## Privacy enforcement

Priority order (highest wins):
1. Folder-level: files in `core/` or `current/` are always PRIVATE
2. File-level: `privacy:` field in frontmatter
3. Default: assume PRIVATE when unclear

Never pass PRIVATE content to an external API.
````

---

### `$BRAIN/_meta/queue.jsonl`

(empty file — no content)

---

### `$BRAIN/_meta/manifest.json`

```json
{
  "generated": null,
  "files": {},
  "tags": {}
}
```

---

### `$BRAIN/core/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/core/identity/profile.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [identity, profile]
title: "Profile"
---

# Profile
> Living document — edit in place. `date` = last updated.

## Basics
- Name:
- Pronouns:
- Location:
- Languages:

## Work / role

## Background

## Preferences & working style

## Notes
```

---

### `$BRAIN/core/identity/goals.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [identity, goals]
title: "Goals"
---

# Goals
> Living document — edit in place. `date` = last updated.

## Horizons (3–5 year)

## Active goals (current quarter)

## Someday / maybe

## Notes
```

---

### `$BRAIN/core/identity/contacts.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [identity, contacts]
title: "Contacts"
---

# Contacts
> Living document — edit in place. `date` = last updated.
> One entry per person. Format: `## First Last` then bullet list of context.

## Template

<!-- Copy and fill for each contact:

## Full Name
- Relationship:
- Context:
- Notes:

-->
```

---

### `$BRAIN/core/health/health.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [health]
title: "Health"
---

# Health
> Living document — edit in place. `date` = last updated.
> Especially sensitive — populate only what you find useful to have here.
> Measurable body parameters live in `body.md`; this file is medical state & habits.

## Conditions
> Chronic or ongoing conditions.

## Allergies & intolerances

## Medications & supplements

## Vaccinations

## Habits & routines
> Sleep, exercise, diet.

## Notes
```

---

### `$BRAIN/core/health/body.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [health, body]
title: "Body parameters"
---

# Body parameters
> Living document — edit in place. `date` = last updated.
> Especially sensitive — populate only what you find useful.
> Medical state and habits live in `health.md`; this file is measurable parameters.

## Static
> Rarely changing.
- Date of birth:
- Height:
- Blood type:

## Current snapshot
> Latest value per metric. `as of` = date of the measurement, not the file edit.
- Weight:             (as of )
- Body fat %:         (as of )
- Resting heart rate: (as of )
- Blood pressure:     (as of )

## Measurement log
> Append-only time-series store. Add one row per measurement; never edit or delete
> past rows. Longitudinal queries ("trend", "average", "since") migrate to
> `db/` + G.I.M.L.I. later (storage-by-question-shape, principle #3). Until then,
> this table is the record.

| Date | Metric | Value | Unit | Notes |
|------|--------|-------|------|-------|

## Notes
```

---

### `$BRAIN/core/finance/finance.md`

```markdown
---
date: YYYY-MM-DDTHH:MM:SS
source: manual
privacy: private
status: active
tags: [finance]
title: "Finance"
---

# Finance
> Living document — edit in place. `date` = last updated.
> This is especially sensitive — populate only what you find useful to have here.

## Overview

## Notes
```

---

### `$BRAIN/current/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/current/inbox/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/current/smeagol/CLAUDE.md`

```markdown
# CLAUDE.md — current/smeagol/

## Purpose
Append-only query log for every G.A.N.D.A.L.F. interaction. Written by
S.M.E.A.G.O.L., read by T.R.E.E.B.E.A.R.D. and future analytics agents.

## Privacy level
**PRIVATE** — logs contain query content and routing details.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| S.M.E.A.G.O.L. | ✅ | Append-only — one entry per Gandalf query |
| T.R.E.E.B.E.A.R.D. | ❌ | Read-only |
| User (manual) | ❌ | Do not edit logs manually |
| Any other source | ❌ | Not allowed |

## Allowed
- Appending new log entries (S.M.E.A.G.O.L. only)
- Reading for analysis

## Not allowed
- Modifying or deleting existing entries — ever
- Retroactive edits of any kind

## File format
JSONL: one JSON object per line, one file per day.
Naming: `YYYY-MM-DD.jsonl`
Fields: `timestamp`, `query_hash`, `route`, `agents_called`, `latency_ms`, `outcome`

## Notes for Claude Code
Read-only for all agents except S.M.E.A.G.O.L.
Do not include log content in API context — use locally only for analysis.
```

---

### `$BRAIN/current/context/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/knowledge/CLAUDE.md`

```markdown
# CLAUDE.md — knowledge/

## Purpose
Curated, processed knowledge base. Content here has been reviewed and is
considered reliable. Primary source for S.A.M.W.I.S.E. retrieval.

## Privacy level
**PUBLIC by default** — content may be included in Claude API context window.
Exception: files with `privacy: private` in frontmatter are treated as PRIVATE.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Preferred — manual curation is highest quality |
| T.R.E.E.B.E.A.R.D. | ✅ | Moving processed inbox items here after review |
| n8n trusted flows | ✅ | Only flows explicitly listed in their own config |
| S.A.M.W.I.S.E. | ❌ | Read-only |
| Other agents | ❌ | Read-only |

## Allowed
- Adding curated notes, articles, summaries with complete frontmatter
- Supersession for updates (`supersedes:` in new file)
- Topic subfolders — create as needed

## Not allowed
- Moving raw `inbox/` content here without processing
- Overwriting existing files
- Files without frontmatter
- Content from `core/` or `current/` without explicit reclassification

## File format
Generated content: `YYYY-MM-DDTHH-MM-SS_source_slug.md`
Living documents: `slug.md`
Frontmatter: `source:` must cite the origin of the information.

## Notes for Claude Code
Primary knowledge source for retrieval agents.
Always check `privacy:` field before including content in API context.
Files with `superseded_by:` set are stale — skip in default queries.
```

---

### `$BRAIN/conversations/CLAUDE.md`

```markdown
# CLAUDE.md — conversations/

## Purpose
Exported AI conversation transcripts (Claude, Gemini, and similar). Source:
browser bookmarklets in `data_providers/chats/`. Each file is one conversation,
processed and stored here for retrieval by S.A.M.W.I.S.E. and Gandalf.

This is the `kb_conversations` collection described in the README memory hierarchy.

## Privacy level
**PRIVATE by default** — conversation content is personal. Files with
`privacy: public` in frontmatter are the exception, not the rule.

MVP note: in the Claude-API MVP, private content may enter the API context window
(see IMPLEMENTATION.md § "Privacy in the Claude-API MVP"). Phase 2 enforces local-only
access for private files.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Via ingest skill or direct paste |
| Ingest skill | ✅ | Bookmarklet output → frontmatter → file here |
| T.R.E.E.B.E.A.R.D. | ✅ | Supersession and archiving only |
| n8n automations | ❌ | Not yet — direct ingest path only |
| Other agents | ❌ | Read-only |

## Allowed
- Adding new conversation files with complete frontmatter
- One file per conversation session; do not merge sessions into one file
- Supersession: if a conversation is re-exported (more complete version), use
  `supersedes:` in the new file

## Not allowed
- Editing conversation content after ingestion — keep the original text intact
- Deleting files

## File format
Naming: `YYYY-MM-DDTHH-MM-SS_bookmarklet_<slug>.md`
Frontmatter: `date`, `source: bookmarklet`, `assistant`, `privacy: private`,
`tags` (≥1), `content_hash` (sha256, for dedup), `title`.
Body layout (canonical order):
1. `## Summary` — 2–4 sentence LLM-generated summary
2. `## Transcript` — raw verbatim transcript, unmodified

Ingestion path: clipboard → `data_providers/chats/incoming/<file>` →
`/ingest-conversation` skill → this folder. The `incoming/` staging folder is
gitignored in the G.A.N.D.A.L.F. repo.

## Notes for Claude Code
Conversations are a primary source for "what did we discuss about X?" queries.
Always check `privacy:` field before including content in API context (Phase 2
enforcement; in MVP, proceed with the content but note it is private).
```

---

### `$BRAIN/archive/CLAUDE.md`

```markdown
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
```

---

### `$BRAIN/db/CLAUDE.md`

```markdown
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
```
