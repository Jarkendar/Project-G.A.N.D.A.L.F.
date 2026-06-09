# ingest-conversation

Ingest AI chat transcripts from the drop folder into `brain/conversations/`.
Each transcript becomes a frontmatter'd markdown file with an auto-generated
summary and tags. Source: bookmarklets in `data_providers/chats/`.

## When to use

- After exporting a conversation using the Claude or Gemini bookmarklet and
  dropping the clipboard output into `data_providers/chats/incoming/`.
- To process a single named file: `/ingest-conversation <filename>`.
- To process all pending files in the drop folder: `/ingest-conversation`.

---

## Clipboard → drop folder (manual step before running this skill)

Run one of these before invoking the skill to land the clipboard content as a
staging file:

```bash
# X11
xclip -selection clipboard -o > data_providers/chats/incoming/$(date +%Y%m%d-%H%M%S).txt

# Wayland
wl-paste > data_providers/chats/incoming/$(date +%Y%m%d-%H%M%S).txt
```

This is the seam a future agent or shell script will automate.

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

### 2. Locate staging files

Staging folder: `data_providers/chats/incoming/` (relative to this project root).
Create it if it does not exist.

If an argument was passed to the skill (e.g. `/ingest-conversation chat.txt`):
- Target = that single file inside `incoming/`. If it does not exist, report error
  and stop.

Otherwise:
- Target = all files directly inside `incoming/`, excluding the `_processed/`
  subfolder and any file whose name starts with `.`.
- If no files found: report "Nothing to do — drop folder is empty." and stop.

### 3. Per-file processing

Repeat steps 3a–3g for each target file.

#### 3a. Read raw transcript

Read the file contents. Call it `$RAW`.

#### 3b. Detect assistant

Count lines in `$RAW` that begin with `Claude: ` (space after colon). Call this
`$CLAUDE_COUNT`. Count lines beginning with `Gemini: `. Call this `$GEMINI_COUNT`.

- If `$CLAUDE_COUNT > $GEMINI_COUNT` → `$ASSISTANT = claude`
- If `$GEMINI_COUNT > $CLAUDE_COUNT` → `$ASSISTANT = gemini`
- Otherwise → `$ASSISTANT = unknown`

#### 3c. Dedup check

Compute the SHA-256 hash of `$RAW` using:

```bash
echo -n "$RAW" | sha256sum | cut -d' ' -f1
```

Call the result `$HASH`. Prefix it: `$CONTENT_HASH = sha256:$HASH`.

Scan every `.md` file in `$BRAIN/conversations/` for a `content_hash:` frontmatter
field matching `$CONTENT_HASH`. Use:

```bash
grep -rl "content_hash: sha256:$HASH" "$BRAIN/conversations/" 2>/dev/null
```

If a match is found:
- Report: "⚠️ Duplicate — `<filename>` matches existing `<matching-file>` (same
  content_hash). Skipping."
- Skip to the next file.

#### 3d. Analyse — generate summary, tags, and title

Read `$RAW` and produce:

1. **Summary:** 2–4 sentences describing what the conversation is about, what
   decisions or conclusions were reached, and any notable outcomes. Write in third
   person, past tense ("The conversation covered…").
2. **Tags:** 3–6 lowercase kebab-case tags. Include the assistant name as a tag
   (e.g. `claude`, `gemini`). Choose the remaining tags from topics, project names,
   or themes evident in the transcript.
3. **Title:** a short (≤60 chars) human-readable title derived from the first `Me:`
   message and the main topic.
4. **Slug:** lowercase kebab-case, ≤40 chars, derived from the title (for the
   filename). Strip stop-words, replace spaces with `-`, remove special chars.

#### 3e. Confirm with user

Show the proposed file before writing:

```
── Proposed ingestion ──────────────────────────────────
File:    YYYY-MM-DDTHH-MM-SS_bookmarklet_<slug>.md
─────────────────────────────────────────────────────────
date:         <ingest datetime ISO 8601>
source:       bookmarklet
assistant:    <claude|gemini|unknown>
privacy:      private
tags:         [<tag1>, <tag2>, …]
content_hash: sha256:<hex>
title:        "<title>"
─────────────────────────────────────────────────────────
Summary:
<2–4 sentence summary>
─────────────────────────────────────────────────────────
Transcript preview (first 3 turns):
<first 3 Me:/Claude: turns>
…
─────────────────────────────────────────────────────────
Write this file? [y / n / edit tags / edit title]
```

- **y** → proceed to 3f.
- **n** → skip this file (leave it in `incoming/`, do not move).
- **edit tags** → prompt for a comma-separated replacement tag list, then re-show
  and ask again.
- **edit title/slug** → prompt for a new title, re-derive slug, re-show and ask again.

#### 3f. Write to brain/conversations/

Compute `$DATETIME` = current datetime in ISO 8601 format (`YYYY-MM-DDTHH-MM-SS`,
colons replaced with dashes in the filename portion but not in the frontmatter value).

Filename: `$BRAIN/conversations/$DATETIME_bookmarklet_$SLUG.md`

Write with this exact body layout:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: bookmarklet
assistant: <claude|gemini|unknown>
privacy: private
tags: [<tag1>, <tag2>, …]
content_hash: sha256:<hex>
title: "<title>"
---

## Summary

<2–4 sentence summary>

## Transcript

<$RAW verbatim — do not modify the transcript content in any way>
```

#### 3g. Move staging file to _processed/

Create `data_providers/chats/incoming/_processed/` if it does not exist.

Move (rename) the staging file there:

```bash
mv "data_providers/chats/incoming/<filename>" \
   "data_providers/chats/incoming/_processed/<filename>"
```

### 4. Report

After all files are processed, print a summary table:

```
── Ingestion report ────────────────────────────────────
✅ Written:   <n> file(s)
⚠️  Skipped:  <n> duplicate(s)
⏭️  Declined: <n> file(s) (user said n)
❌ Errors:   <n>
```

For each written file, print the full path in `$BRAIN/conversations/`.

---

## Notes

- The `incoming/` folder is gitignored in this repo — raw transcripts (which are
  private) never enter the G.A.N.D.A.L.F. git history.
- The skill does **not** update `_meta/queue.jsonl` or `_meta/manifest.json` — that
  is Bilbo/Treebeard territory, deferred.
- The canonical raw transcript lives in the `brain/` file under `## Transcript`.
  The `_processed/` copy is a convenience fallback only.
- Privacy: in the Claude-API MVP, transcript content enters the API context window
  for summary/tag generation. This is the accepted MVP exception — see
  `IMPLEMENTATION.md § "Privacy in the Claude-API MVP"`.
