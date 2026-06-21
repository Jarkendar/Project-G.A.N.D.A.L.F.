---
name: interview
description: >-
  Conduct a structured, adaptive Q&A session to elicit knowledge on any topic,
  then store the result in the right place in brain/ — an existing core/
  living document, an existing knowledge/ topic, or a new knowledge/ file.
  Questions are generated from the topic at runtime, never hardcoded. Use this
  skill to capture structured knowledge the user holds but hasn't written
  down, to fill gaps in an existing brain/ document through conversation
  rather than direct editing, or to record personal facts across any domain
  (health, finances, projects, technical knowledge, people, experiences).
---

# interview

Conduct a structured, adaptive Q&A session to elicit knowledge on any topic, then
store the result in the appropriate place in `brain/`. The skill supplies the
process — questions are generated from the topic at runtime, never hardcoded.

## When to use

- Capturing structured knowledge about a topic that the user holds in their head
  but has not yet written down
- Filling gaps in an existing `brain/` document through conversation rather than
  direct editing
- Recording personal facts across any domain — health, finances, projects,
  technical knowledge, people, experiences

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
Call it `$BRAIN`. Verify `$BRAIN` exists; if not, tell the user to run
`/init-brain` first, then stop.

### 2. Establish the topic

If the skill was invoked with an argument (e.g. `/interview my career history`),
use that as the topic. Otherwise ask:

> "What topic do you want to capture today?"

Call the result `$TOPIC`.

### 3. Survey brain/ for a match (adaptive routing)

Route `$TOPIC` to exactly one target. Work through the options in order:

#### 3a. Check core/ routing table

Does `$TOPIC` map to one of the six living documents?

| Category | Target file |
|---|---|
| Identity — name, location, role, languages, background, preferences | `$BRAIN/core/identity/profile.md` |
| Goals — horizons, active goals, someday/maybe | `$BRAIN/core/identity/goals.md` |
| Contacts — people, relationships, context | `$BRAIN/core/identity/contacts.md` |
| Health — conditions, allergies, meds, vaccinations, habits | `$BRAIN/core/health/health.md` |
| Body parameters — height, weight, body composition, vitals, measurement log | `$BRAIN/core/health/body.md` |
| Finance — accounts, budget, financial notes | `$BRAIN/core/finance/finance.md` |

If yes → target type **(a) core/ document**. Read the target file (if it exists)
to understand what is already there.

#### 3b. Scan knowledge/ for an existing topic

If no core/ match was found, search `knowledge/` for relevant material:

```bash
# Look for subfolder names and filenames
find "$BRAIN/knowledge" -type d | sed "s|$BRAIN/knowledge/||"
find "$BRAIN/knowledge" -name "*.md" | sed "s|$BRAIN/knowledge/||"

# Look inside files for matching tags or title
grep -rl "$TOPIC_KEYWORDS" "$BRAIN/knowledge/" 2>/dev/null
```

Use the topic keywords (key nouns from `$TOPIC`) for the grep scan. Read short
excerpts (frontmatter + first heading) of any candidate files.

If one or more relevant documents are found → target type **(b) knowledge/
existing**. Select the best match; present it to the user.

#### 3c. New topic

If neither 3a nor 3b found a match → target type **(c) new topic**.

Propose a new location:
```
$BRAIN/knowledge/<topic-slug>/
```
where `$TOPIC_SLUG` is a lowercase kebab-case slug derived from `$TOPIC`
(≤40 chars, strip stop-words, replace spaces with `-`, remove special chars).

#### 3d. Show routing result and confirm

Present the routing decision before asking any interview questions:

```
── Routing ──────────────────────────────────────────────
Topic:   <$TOPIC>
Target:  <(a) $BRAIN/core/…  |  (b) $BRAIN/knowledge/…  |  (c) new: $BRAIN/knowledge/<slug>/>
Mode:    <append to existing document | new document>
─────────────────────────────────────────────────────────
Continue with this target? [y / redirect]
```

On `y`: proceed to step 4.
On `redirect`: ask the user where they want to store it, then continue.

### 4. Plan the interview

Generate an adaptive question outline tailored to `$TOPIC`:

- **For target (a) core/ document:** read the file and identify **gaps** —
  sections that are empty, templated, or thin. Derive questions to fill those gaps.
  Do not ask about information that is already present.
- **For target (b) knowledge/ existing:** read the document and identify what is
  missing or could be deepened. Questions should extend, not duplicate.
- **For target (c) new topic:** generate a comprehensive initial outline. Group
  questions by theme (e.g. background, current state, plans, constraints).

Present the outline to the user:

```
── Interview outline ─────────────────────────────────────
<numbered list of question themes / individual questions>
─────────────────────────────────────────────────────────
Adjust this outline? [y = edit  |  n = start]
```

On `n`: proceed to step 5.
On `y`: let the user add, remove, or reorder questions, then proceed.

The outline is a guide, not a script. Follow the conversation; adapt on the fly.

### 5. Conduct the interview

Ask questions one at a time, or in small natural batches (2–3) when they are
tightly related. After each answer:

- Follow up if the answer is vague, partial, or opens a new angle worth exploring.
- Offer to skip if the user seems unwilling or unable to answer.
- Accept "don't know", "skip", or "move on" without pressing.

The user can end the interview at any point by saying "done", "that's enough", or
similar.

**Rules:**
- Do not invent facts. Every piece of knowledge must come from the user.
- Do not summarise or interpret during the interview — capture faithfully.
- Keep a running internal record of `Q:` / `A:` pairs throughout.

### 6. Synthesise

When the interview ends, prepare the output. Format depends on the target type.

#### Target (a) core/ document — in-place edit

Read the full current file. Integrate the new facts into the appropriate sections,
matching the existing markdown structure and style exactly:

- Edit in place — do not create a new file.
- Preserve all existing content verbatim; add to it, never overwrite.
- Match the comment density, list style, and heading hierarchy of the surrounding
  content.
- **`body.md` exception:** `## Current snapshot` fields are edited in place;
  rows in `## Measurement log` are **append-only** (never edit or delete a past row).
- After editing, update the `date:` frontmatter field to the current ISO 8601
  datetime.

#### Target (b) knowledge/ existing — extend or supersede

Read the current document. Choose the approach:

- **Extend in place** (default for additions): insert new facts into the relevant
  sections, matching the document's style. Bump `date:` frontmatter.
- **Supersession** (for material revision — new version replaces the old one):
  create a new file with `supersedes: <old-path>` in frontmatter. Use the same
  naming convention: `YYYY-MM-DDTHH-MM-SS_interview_<slug>.md`.

Offer supersession if the interview substantially changes or replaces the existing
content; default to in-place extension.

#### Target (c) new topic — new file

Default document format:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: interview
privacy: <public|private>
tags: [<tag1>, <tag2>, …]
title: "<human-readable title>"
status: active
---

# <Title>

## Synthesis

<Knowledge organised by theme, not chronologically. 2–5 paragraphs or structured
bullet sections depending on the topic.>

## Interview Q&A

Q: <question asked>
A: <answer given verbatim>

Q: …
A: …
```

If the topic clearly calls for a different structure (e.g. a reference table, a
timeline, a list of entries), propose that format to the user before writing.

After drafting, generate:
- **Tags:** 3–6 lowercase kebab-case tags derived from the topic and answers.
  Include at least one topical tag and `interview`.
- **Title:** ≤60 chars, human-readable, derived from `$TOPIC`.
- **Privacy:** ask the user explicitly — `public` or `private`?
  (Default suggestion: `private` if the topic touches personal details; `public`
  otherwise.)

### 7. Privacy gate — confirm before writing

Before any file is written, show the user a preview:

```
── Proposed write ───────────────────────────────────────
File:    <full path>
Mode:    <edit in place | new file | supersession>
Privacy: <public | private>
──────────────────────────────────────────────────────────
<For core/ targets only:>
⚠️  core/ content is PRIVATE and stays on this machine. In the MVP it may
    enter the Claude API context window (see IMPLEMENTATION.md §
    "Privacy in the Claude-API MVP"). Phase 2 closes this exception.
──────────────────────────────────────────────────────────
Change summary:
<short description of what will be added or changed>
──────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write (step 8).
- **n** → discard everything, stop. Nothing is written.
- **edit** → let the user correct the synthesised content, then re-show and ask
  again.

### 8. Write

Execute the write matching the target type:

**core/ document (target a):**
- Edit the file in place using the synthesised content.
- Update `date:` frontmatter to the current ISO 8601 datetime.
- Offer optional supersession-archive for substantial changes (same as
  `/update-core` step 7): copy the pre-edit version to
  `$BRAIN/archive/YYYY-MM-DDTHH-MM-SS_superseded_<slug>.md` and add
  `supersedes:` to the new frontmatter. Default: skip, edit in place.

**knowledge/ existing (target b):**
- In-place edit: write the updated document, bump `date:`.
- Supersession path: write the new file at
  `$BRAIN/knowledge/<subfolder>/YYYY-MM-DDTHH-MM-SS_interview_<slug>.md` with
  `supersedes: <old-path>` in frontmatter.

**knowledge/ new (target c):**
- Create the subfolder `$BRAIN/knowledge/$TOPIC_SLUG/` if it does not exist.
- Write `$BRAIN/knowledge/$TOPIC_SLUG/YYYY-MM-DDTHH-MM-SS_interview_$SLUG.md`
  with the full document from step 6.

### 9. Report

After writing, print:

```
── Interview complete ───────────────────────────────────
✅ Written:  <full path>
   Sections: <section(s) added or modified>
   date:     <new value>
   Privacy:  <public | private>
```

---

## Notes

- **Universal by design.** Questions are generated from the topic at runtime, never
  hardcoded here. The skill provides the process; the content is always the user's.
- **core/ targets reuse `/update-core` conventions.** This skill does not create a
  parallel path for core/ documents. The same living-document rules, confirmation
  flow, and privacy gate apply.
- **No invented facts.** Every piece of knowledge must come explicitly from the
  user's answers. If an answer is ambiguous, ask rather than infer.
- **Skippable questions.** The user can skip any question without stopping the
  interview. A partial interview is better than no interview.
- **Does not touch `_meta/`.** `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory — this skill does not update them.
- **Multi-session interviews out of scope (v1).** There is no draft/resume
  mechanism. If an interview is interrupted, the collected answers so far are
  presented for confirmation; the user can write the partial result or discard it.
- **Privacy default: ask.** For new knowledge/ files, always ask the user
  explicitly. Do not assume public for topics that may touch personal details.
