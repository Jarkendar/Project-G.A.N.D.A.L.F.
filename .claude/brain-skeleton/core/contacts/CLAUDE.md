# CLAUDE.md — core/contacts/

## Purpose
People directory: relationships, context, interests, key facts about people in my life.

## Privacy level
**PRIVATE** — same as all `core/` content. Never pass to external APIs.
MVP exception: may enter Claude API context window — see IMPLEMENTATION.md.

## Structure (two-layer)

| File | Purpose |
|---|---|
| `contacts.md` | Role index — one row per person; fast grep for "who is X" queries |
| `<slug>.md` | Per-person detail — interests, notes, dates; read only when the person is relevant |

**How queries resolve:**
- "Who is my partner?" → grep `contacts.md` → find `[[jan-kowalski]]`
- "What should I buy them?" → read `core/contacts/jan-kowalski.md`

## Document model
Same living-document model as `core/identity/`.
- `contacts.md` — **role index**: append rows, never delete.
- Individual `<slug>.md` — **living documents**: edit in place, bump `date:`.
- New contacts: `/add-contact` skill (to be written) or manual edit.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Any file |
| `/add-contact` skill | ✅ | With user confirmation |
| `/update-core` skill | ✅ | For individual detail files |
| Other CC agents | ❌ | Read only |

## Required frontmatter (all files)
```yaml
date: <last-updated, ISO 8601>
source: manual
privacy: private
status: active
tags: [contacts, <role-tag>]
```

## Not allowed
- Deleting any file
- Writing without frontmatter
