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
