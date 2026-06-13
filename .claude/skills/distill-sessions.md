# distill-sessions

Read saved conversations from `brain/conversations/` and extract knowledge worth
promoting to permanent `brain/` files. For each piece of extracted knowledge,
propose a specific addition to the appropriate brain file, show a preview, and
ask for confirmation before writing. Nothing is written without explicit approval.

This is the primary mechanism for turning conversational history into structured,
queryable knowledge. It corresponds to E3 + E5 from IMPLEMENTATION.md.

## When to use

- After accumulating several sessions (weekly review, or whenever `brain/` feels
  stale relative to what you've been working on).
- After a session that produced a significant decision, new personal fact, or
  domain knowledge you want to retain.
- On demand: `/distill-sessions` — processes all unprocessed conversations.
- Scoped: `/distill-sessions 7d` — last 7 days. `/distill-sessions 30d` — last
  30 days. `/distill-sessions <filename>` — one specific file.

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

Resolve the path. Call it `$BRAIN`. Verify `$BRAIN/conversations/` exists; if
not, prompt to run `/init-brain`, then stop.

### 2. Select conversation files

**No argument:** find all `.md` files in `$BRAIN/conversations/` whose frontmatter
contains `distilled: false`. Use:

```bash
grep -rl "distilled: false" "$BRAIN/conversations/" 2>/dev/null | sort
```

**`Nd` argument (e.g. `7d`, `30d`):** find files modified in the last N days,
regardless of `distilled:` status:

```bash
find "$BRAIN/conversations/" -name "*.md" -mtime -N | sort
```

**Filename argument:** use that single file directly (full or relative path within
`$BRAIN/conversations/`).

If no files match: report "Nothing to distill — no unprocessed conversations found."
and stop.

Report how many files will be processed before starting:

```
── Distilling N conversation(s) ────────────────────────
<list of filenames, one per line>
─────────────────────────────────────────────────────────
Continue? [y / n]
```

### 3. Read and analyse all selected files

Read every selected conversation file in full. Then perform a single consolidated
analysis across all files to extract **knowledge nuggets** — discrete, durable
facts or insights worth adding to `brain/`.

A knowledge nugget is worth extracting when it is:
- A personal fact (role, preference, location, status) → `core/identity/profile.md`
- A goal, priority, or horizon change → `core/identity/goals.md`
- A contact detail or relationship note → `core/contacts/<slug>.md`
- A health, body, or fitness datum → `core/health/*.md`
- A financial fact, account, or position → `core/finance/finance.md`
- A domain concept or reference note (technology, finance, methodology) →
  `knowledge/<domain>/<topic>.md` (create the file if it does not exist)
- A project decision or architectural conclusion → `knowledge/projects/<name>.md`
  or inline note in an existing `knowledge/` file

Do NOT extract:
- Conversational filler, small talk, or meta-discussion about the assistant
- Facts already present in the target file (check before proposing)
- Speculative or uncertain statements (unless explicitly flagged as hypotheses)
- Task lists or TODOs (those belong in `_meta/queue.jsonl`, not knowledge files)
- Anything the user explicitly said was tentative or subject to change

For each nugget, record:
- `nugget_text` — the extracted knowledge, verbatim or lightly cleaned
- `source_file` — which conversation file it came from
- `target_file` — which `brain/` file it should go into (full path)
- `target_section` — which section header (if applicable)
- `proposed_addition` — the exact text to insert, formatted to match the target
  file's style (bullet, sentence, table row, etc.)
- `category` — one of: `personal-fact`, `goal`, `contact`, `health`, `finance`,
  `domain-knowledge`, `project-decision`
- `confidence` — `high` (clearly stated), `medium` (inferred), `low` (uncertain)

Group nuggets by `target_file` for the review step.

### 4. Read current content of each target file

Before proposing any addition, read the current content of each target file.
This is required to:
- Confirm the fact is not already present (skip if it is)
- Match the formatting style exactly
- Place the addition in the right section

For target files that do not yet exist in `brain/` (new `knowledge/` files),
note that the file will be created.

### 5. Review and confirm — nugget by nugget

For each `target_file`, process its nuggets one by one. Show:

```
── Knowledge nugget ─────────────────────────────────────
Source:    <source_file>
Category:  <category>
Target:    <target_file>
Section:   <target_section or "new file">
Confidence: <high|medium|low>
─────────────────────────────────────────────────────────
Fact:
  <nugget_text>
─────────────────────────────────────────────────────────
Proposed addition:
  <proposed_addition — formatted exactly as it would appear in the file>
─────────────────────────────────────────────────────────
[y] Write  [n] Skip  [e] Edit  [s] Skip all for this file  [q] Stop
```

On **y**: queue the write. Do not write yet — collect all approvals, then write
in batch (step 6).

On **n**: discard this nugget, continue.

On **e**: show the proposed addition in an editable form. Accept the user's
correction. Re-show the updated nugget and ask again.

On **s**: skip all remaining nuggets for this target file, move to the next.

On **q**: stop reviewing. Write all already-approved nuggets (step 6), then stop.
Report how many nuggets were skipped.

If a nugget has `confidence: low`, prefix the display with:
`⚠️  Low confidence — this was inferred, not stated directly.`

### 6. Apply approved additions

For each approved nugget, in order of target file:

**Existing files:** insert the proposed addition into the correct section.
Rules identical to `/update-core` step 5:
- Edit in place, preserve all other content verbatim
- Match existing markdown style
- Do not delete existing content
- If the target section does not exist, append a new section at the end

**New `knowledge/` files:** create the file with minimal frontmatter and the
nugget as the first content:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: distilled
privacy: <private if from core/ topics, otherwise knowledge>
tags: [<derived from category and topic>]
---

## <topic title>

<proposed_addition>
```

**`core/` files:** after each write, bump the `date:` frontmatter field to the
current ISO 8601 datetime (same rule as `/update-core` step 6).

### 7. Mark conversations as distilled

After all writes are complete, update the `distilled:` frontmatter field in each
processed conversation file from `false` to the current date (`YYYY-MM-DD`):

```bash
sed -i "s/^distilled: false$/distilled: $(date +%Y-%m-%d)/" "$CONVERSATION_FILE"
```

Do this for every file selected in step 2, regardless of whether any nuggets were
extracted from it (even a conversation with no extractable knowledge should be
marked so it is not re-processed next time).

### 8. Report

```
── Distillation complete ───────────────────────────────
Conversations processed: <N>
Nuggets found:           <N>
  Written:    <N>
  Skipped:    <N>
  Edited:     <N>

Brain files updated:
<bulleted list of files written, with count of additions each>

New knowledge files created:
<bulleted list, or "(none)">
─────────────────────────────────────────────────────────
```

---

## Notes

- **Nothing is written without confirmation.** Every nugget goes through step 5.
  The user can reject any individual nugget or stop the entire review mid-way.
- **`distilled: false/date` is the processing marker.** `/save-session` writes
  `distilled: false`; this skill flips it. Conversations imported via
  `/ingest-conversation` do not have this field — they will not be picked up by
  the no-argument invocation (which filters on `distilled: false`). Use a date-range
  argument to include them: `/distill-sessions 30d`.
- **Privacy routing.** Nuggets extracted from sessions that touched `core/` are
  treated as `privacy: private` regardless of category. When in doubt, default
  to private — the user can downgrade later.
- **Knowledge files are open-form.** Unlike `core/` living documents, `knowledge/`
  files have no fixed template. Match whatever style exists in the file; for new
  files, use minimal frontmatter and clear section headers.
- **Idempotent reads.** This skill reads many files from `brain/` before writing
  anything. The read phase is safe to interrupt — no state is changed until step 6.
- **Confidence levels exist to surface uncertainty, not to suppress it.** Even
  `low`-confidence nuggets are shown to the user — they may know something that
  makes them worth keeping. The flag is just a warning, not a filter.
- **Relation to E3 and E5 (IMPLEMENTATION.md).** This skill is the manual
  forerunner of both: E3 (FTS5 log retrieval) and E5 (agent-curated profile
  updates). When Smeagol's logs exist and Samwise is operational, this workflow
  will be partially automated — but the human-review gate at step 5 is permanent.
