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
