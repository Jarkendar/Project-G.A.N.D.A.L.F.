# save-session

Save the current Claude Code session to `brain/conversations/` as a structured
summary. Unlike `/ingest-conversation` (which ingests exported web-chat transcripts
via bookmarklet), this skill captures a live CC session from the current context
window — no export step required.

Run at the end of a session, or at any checkpoint worth preserving.

## When to use

- At the end of a Claude Code session — before closing the terminal or starting
  unrelated work.
- After a significant decision or design discussion, even mid-session.
- Any time you want a record of what was just discussed and decided.

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
Call it `$BRAIN`. Verify `$BRAIN/conversations/` exists; if not, prompt to run
`/init-brain` first, then stop.

### 2. Synthesize the session

Analyse the entire current conversation context and produce:

**2a. Title** — ≤60 chars, human-readable, describes the session's main topic or
outcome. Example: "Finance skill design and brain scaffold review".

**2b. Slug** — lowercase kebab-case, ≤40 chars, derived from the title. Strip
stop-words, replace spaces with `-`, remove special chars.

**2c. Comprehensive summary** — 4–8 paragraphs covering:
- What was the starting point / user's goal for this session
- What was discussed, explored, or decided (with enough detail to reconstruct
  context in a future session — not just "we discussed X", but *what* about X
  and *what conclusion*)
- Any architectural, design, or strategic decisions made (including rejected
  alternatives, if noteworthy)
- Files created, modified, or deleted and *why*
- Open questions or next steps explicitly mentioned
- Anything unusual, surprising, or worth flagging for future reference

Write in third person, past tense ("The session covered…", "The user decided…").
Be generous — a summary that is too short loses context; one that is too long costs
only disk space.

**2d. Topics** — 3–8 lowercase kebab-case tags describing the subject matter.
Include the primary project or domain (e.g. `gandalf`, `brain`, `finance`,
`job-search`). Do not include `claude` as a tag (it is implied by `source: cc-session`).

**2e. Brain files touched** — list any `brain/` files that were read from or
written to during this session (absolute paths, one per line). Empty list if none.

**2f. Outcome flag** — one of:
- `productive` — substantive work was done or decisions were made
- `exploratory` — brainstorming, no firm conclusions
- `blocked` — session ended waiting on something external
- `partial` — work in progress, session saved mid-task

### 3. Dedup check

Compute a SHA-256 hash of the summary text from step 2c:

```bash
echo -n "$SUMMARY" | sha256sum | cut -d' ' -f1
```

Call the result `$HASH`. Prefix: `content_hash: sha256:$HASH`.

Scan `$BRAIN/conversations/` for an existing file with the same `content_hash`:

```bash
grep -rl "content_hash: sha256:$HASH" "$BRAIN/conversations/" 2>/dev/null
```

If a match is found: report a warning and ask whether to continue or abort.
(Unlike `/ingest-conversation`, two CC sessions can legitimately be about the
same topic with nearly identical summaries — so skip rather than hard-block.)

### 4. Confirm with user

Show the proposed file before writing:

```
── Proposed session record ─────────────────────────────
File:    YYYY-MM-DDTHH-MM-SS_cc_<slug>.md
─────────────────────────────────────────────────────────
date:         <current ISO 8601>
source:       cc-session
outcome:      <flag>
tags:         [<tag1>, <tag2>, …]
content_hash: sha256:<hex>
title:        "<title>"
─────────────────────────────────────────────────────────
Summary:
<full summary text>
─────────────────────────────────────────────────────────
Brain files touched:
<list or "(none)">
─────────────────────────────────────────────────────────
Write this record? [y / n / edit summary / edit tags]
```

- **y** → proceed to step 5.
- **n** → discard, stop.
- **edit summary** → show the summary, accept freeform corrections, re-confirm.
- **edit tags** → prompt for replacement tags, re-confirm.

### 5. Write to brain/conversations/

Filename: `$BRAIN/conversations/$DATETIME_cc_$SLUG.md`

where `$DATETIME` = current datetime formatted as `YYYY-MM-DDTHH-MM-SS`
(colons replaced with dashes in the filename, preserved in the frontmatter value).

Write with this exact body:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: cc-session
outcome: <productive|exploratory|blocked|partial>
privacy: private
tags: [<tag1>, <tag2>, …]
content_hash: sha256:<hex>
title: "<title>"
distilled: false
---

## Summary

<comprehensive summary — 4–8 paragraphs>

## Brain files touched

<bulleted list of brain/ paths accessed, or "(none)">

## Open items

<bulleted list of open questions or next steps mentioned during the session,
or "(none)">
```

### 6. Report

```
── Session saved ────────────────────────────────────────
✅  Written: <full path>
    Title:   <title>
    Outcome: <flag>
    Tags:    <tags>

Run /distill-sessions to extract knowledge from saved conversations.
─────────────────────────────────────────────────────────
```

---

## Notes

- **Source distinction.** `source: cc-session` distinguishes CC sessions from
  `source: bookmarklet` (web-chat exports). Both land in `brain/conversations/`,
  making them jointly searchable by `/distill-sessions` and future FTS5 queries (E3).
- **No raw transcript.** This skill saves a synthesised summary, not a verbatim
  transcript. The CC conversation lives in the context window — there is no stable
  text to dump. A good summary is more useful for future retrieval than a raw dump.
- **`distilled: false`** frontmatter field marks this file as not yet processed
  by `/distill-sessions`. The harvest skill flips it to the date of extraction.
- **Privacy.** Session summaries are `privacy: private` by default. They may
  describe work done on personal data (core/ files, finance, health). Do not
  downgrade privacy without explicit user instruction.
- **No queue / manifest updates.** Bilbo and Treebeard territory — not touched here.
