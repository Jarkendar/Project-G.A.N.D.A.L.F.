# schema.md — brain/ frontmatter specification

All markdown files in `brain/` must include YAML frontmatter. This document
is the canonical specification.

## Required fields

```yaml
date: 2026-06-08T14:30:00    # ISO 8601, creation datetime
source: manual               # who/what created this file
                             # values: manual | n8n/<flow-name> | bookmarklet | treebeard | interview
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
