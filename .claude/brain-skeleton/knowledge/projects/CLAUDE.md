# CLAUDE.md — knowledge/projects/

## Purpose

Project-related knowledge. This folder holds **two distinct content types**
that share the same directory and naming convention (`<slug>.md`) but have
different schemas, writers, and privacy defaults — read the `kind:` field (or
its absence) before treating a file as one or the other.

## Content type 1 — Project reference pages

Hand-written reference pages for already-existing or shipped projects/repos —
what it is, its architecture, its status. Manually curated; highest quality.

**Frontmatter (no `kind` field):**
```yaml
date: <ISO8601>
source: manual
privacy: public          # override to private if the content warrants it
status: active
tags: [projects, <topic tags>]
title: "<Project title>"
```

**Writers:** user (manual) only.

## Content type 2 — Idea dossiers

Researched dossiers produced by the `develop-idea` skill for a project idea
that does not exist yet: feasibility assessment, prior-art research, a
proposed execution scenario, future expansion ideas, and a personalized
skill-growth assessment. See `.claude/skills/develop-idea/SKILL.md` for the
full body template and workflow.

**Frontmatter (`kind: idea-dossier` present):**
```yaml
date: <ISO8601>
updated: <ISO8601>
source: develop-idea
privacy: private          # always — explicit override of the folder default
kind: idea-dossier
status: active
origin: inline | backlog
backlog_ref: backlog/projects/<slug>.md   # only when origin: backlog
effort: <S|M|L|XL|->
tags: [projects, idea-dossier, <topic tags>]
title: "<Idea title>"
```

**Writers:** `develop-idea` skill only; gate before every write.

## Privacy level

**Mixed, by design** — unusual for `knowledge/`. Reference pages default
`public` (may reach the Claude API context window); idea dossiers are always
`private` (personal feasibility/skill-growth assessment). Always check the
file's own `privacy:` field before treating content as shareable — do not
assume folder-level public applies uniformly here.

## File naming

`<slug>.md` — lowercase kebab-case, derived from the project/idea title.
Both content types share this convention, which is why `develop-idea` runs a
collision check (see its SKILL.md, step 5) before writing: a slug match
without `kind: idea-dossier` means it hit an existing reference page, not a
prior dossier, and must not be overwritten.

## Relationship to backlog/projects/

An idea dossier is often the researched successor to a
`backlog/projects/<slug>.md` capture (see `backlog/CLAUDE.md`). When promoted
via `develop-idea`, the backlog item is marked `status: done` with a
`promoted_to:` pointer — it stays in place, it is not deleted.
