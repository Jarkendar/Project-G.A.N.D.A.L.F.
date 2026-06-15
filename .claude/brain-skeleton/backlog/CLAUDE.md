# CLAUDE.md — backlog/

## Purpose
Personal idea and to-do capture. One file per idea — descriptive filename,
lightweight frontmatter, 2–6 lines of context. Used when reviewing what to
do next or planning activities across any domain of life.

This is **not** a dev backlog for G.A.N.D.A.L.F. itself (that lives in
`IMPLEMENTATION.md`), nor high-level life goals (those live in
`core/identity/goals.md` § Someday/maybe). This is operational,
granular, and domain-spanning.

## Privacy level
**PRIVATE** — treat all content as private. Folder-level rule takes precedence
over any file-level `privacy:` field.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Valid frontmatter required |
| `/idea` skill | ✅ | Only writer agent; gate before every write |
| T.R.E.E.B.E.A.R.D. | read-only | Does not move or consolidate backlog items |
| Other CC agents | read-only | No writes |

## Status lifecycle

```
idea → active → done
             ↘ dropped
```

- `idea` — captured, not yet started
- `active` — in progress
- `done` — completed; file stays in place (append-only)
- `dropped` — abandoned; file stays in place

Items do not move between subfolders when status changes. To promote a
`done` item into permanent knowledge, use `/idea list` → promote action
(copies to `knowledge/projects/`, marks original as promoted).

## Subfolders

| Subfolder | What goes here |
|---|---|
| `projects/` | Ideas for software, homelab, or creative projects |
| `activities/` | Free-time ideas, new activities, trips, experiences |
| `check/` | Things to research, read, verify, or look into |
| `create/` | Things to make: recipes, 3D prints, tools, documents |
| `remember/` | Reminders without a hard date — things not to forget |
| `notes/` | Loose notes / catch-all when nothing else fits |

New subfolders can be added as needed — update this table when you do.

## File format

Naming: `<descriptive-kebab-slug>.md` (domain = subfolder, no prefix needed)

Required frontmatter:
```yaml
date: <ISO8601 — creation>
updated: <ISO8601 — last status change>
source: idea
privacy: private
status: idea          # idea | active | done | dropped
domain: <subfolder>   # mirrors the subfolder name
tags: [tag1, tag2]
title: "..."
```

Optional:
```yaml
effort: M             # S | M | L | XL (rough estimate)
promoted_to: knowledge/projects/<slug>.md   # set when promoted
```

Body: 2–6 lines — what the idea is, why/context, optional first step.
