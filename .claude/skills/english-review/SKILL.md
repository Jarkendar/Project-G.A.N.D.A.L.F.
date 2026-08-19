---
name: english-review
description: >-
  Analyze an English-practice transcript (Gemini Live conversational drills)
  or a free-form debrief of a real English call, and merge the findings into
  the living log at brain/knowledge/language/english.md — recurring error
  categories with counts, a work/casual phrasebook, and a listening-miss log
  for comprehension failures. Use this skill right after a Gemini Live
  practice session, after a real work call conducted in English that didn't
  go well, or whenever there's a transcript with "Me:" / assistant speaker
  labels to analyze for grammar, vocabulary, and fluency patterns.
---

# english-review

Turns a raw English-practice transcript — or a plain debrief of a real call — into
durable, trend-able data: a categorized error log, a work/casual phrasebook, and
(when comprehension was the problem, not production) a listening-miss log. Distinct
from `/ingest-conversation`, which archives the raw transcript verbatim into
`brain/conversations/` — this skill does not duplicate that archiving; it only
reads the transcript to extract structured learning signal.

## When to use

- Right after a Gemini Live (or similar) English conversation-practice session.
- After a real work call in English that went badly, even with no transcript —
  just a debrief in your own words.
- Whenever you have text with `Me:` / assistant speaker labels to analyze.

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
Call it `$BRAIN`. If `$BRAIN` does not exist:
- Tell the user to run `/init-brain` first.
- Stop.

If `$BRAIN/knowledge/language/` does not exist:
- Offer to create it (`mkdir` + a minimal `CLAUDE.md`: "PRIVATE — English practice
  log and self-assessed weaknesses tied to recruitment. Living documents, edited
  in place."). Proceed only after confirmation.

### 2. Gather the input

- `/english-review <pasted text>` — the text is the raw transcript or debrief.
- `/english-review <path>` — if it resolves to an existing file, read it. Also
  check `data_providers/chats/incoming/` for an unprocessed transcript if the
  argument names a bare filename found there.
- `/english-review` (no argument) — ask: "Wklej transkrypt (Gemini Live / inne) albo
  opisz rozmowę, jeśli nie masz transkryptu."

### 3. Detect mode

- **Transcript mode** — the input has speaker labels (`Me:` and an assistant name,
  e.g. `Gemini:`). Multiple transcripts may be pasted together (e.g. "rozmowa nr 1",
  "rozmowa nr 2") — treat each as a separate session for the session log, but pool
  errors into one analysis pass unless the user distinguishes them.
- **Debrief mode** — free prose describing a real call, no speaker-labeled
  transcript. Skip step 5 (no error table to build — there's no verbatim "Me:"
  text to correct). Go straight to step 6 (listening).

If a transcript mode input also describes a comprehension failure (the user's own
commentary, not the transcript content), run **both** step 5 and step 6.

### 4. Run the analysis (transcript mode)

Apply this prompt to the `Me:` lines only — ignore all assistant lines except to
understand context:

```
You are an English language coach specializing in spoken fluency and
comprehension analysis.

I will paste a transcript of an English conversation. The transcript contains
speaker labels (Me: / <Assistant>:). Focus your analysis ONLY on lines starting
with "Me:" — ignore all assistant responses except as context.

## Part 1 — Error log

For each mistake, produce a row:

| # | What I said | Corrected version | Kategoria | Rejestr | Note |
|---|---|---|---|---|---|

Rules:
- "What I said" — the full sentence or phrase, exactly as in the transcript.
- "Corrected version" — the corrected full sentence, even if only one word was
  wrong. Never correct just the single word in isolation.
- "Kategoria" — exactly one of: articles, tense, prepositions, false-friends,
  relative-pronouns, passive, word-order, plural-agreement, polish-filler,
  tech-vocab, restarts.
- "Rejestr" — work (technical/professional context) or casual (everyday/social).
- "Note" — short explanation, in Polish.
- Include grammar errors, wrong word choice, unnatural phrasing, missing
  articles/prepositions.
- Skip very minor issues that wouldn't confuse a native speaker.

## Part 1b — Technical terminology check

Separately flag any misused domain/technical term — even if the conversation
partner accepted or echoed it back approvingly. Assistants grading fluency
often don't catch domain-specific errors. Example: describing a local-cache-
then-sync architecture as "online first" when the correct term is
"offline-first" is a technical error, not a fluency one — flag it as
`tech-vocab` in the table above, don't just note it separately.

## Part 1c — Abandoned sentences

Count sentences that were restarted or trailed off mid-thought (filler words,
"for... for...", repeated false starts). List a few representative examples.
This is a fluency signal distinct from grammar — track it separately, don't
fold it into the error table.

## Part 2 — Pattern analysis

Write a short analysis (5-8 sentences) in Polish covering:
- Which error categories repeat, with rough counts per category
- Any structural sentence-construction patterns that sound non-native
- Two things to focus on practicing next, prioritized by frequency × how much
  they'd confuse a native listener

## Part 3 — Counts (for trend tracking, not a single invented score)

- Total "Me:" words (rough count)
- Errors per 100 words
- Errors per category
- Abandoned-sentence count
- Polish filler-word count (e.g. "uh", "eee", "no", direct calques)

## Format rules
- Respond in Polish, except English content in table cells.
- Part 1/1b as a table, Part 1c as a short list, Part 2 as prose, Part 3 as a
  compact list.

---
Transcript:
[the Me:/assistant transcript]
```

Run this inline — do not shell out or call an external API; you are the coach.

### 5. Speaking output

Present the Part 1/1b/1c/2/3 results to the user before writing anything.

### 6. Listening output (debrief mode, or flagged in step 3)

Ask (batched, single message, skip any already answered by the input):
- What was missed or misunderstood — content, not just "I didn't understand"?
- Best guess at cause: accent, speaking speed, technical vocabulary, or audio
  quality (bad mic/connection)?
- Did you ask for repetition/clarification, or let it go?

Produce a **Listening miss** entry: date, context (who/what call), cause, what
was missed, and — if the cause was audio quality rather than the user's own
comprehension — say so plainly rather than attributing it to a language gap.

### 7. Build the write plan

```
── english-review — proposed update ────────────────────────────────────
Target: $BRAIN/knowledge/language/english.md
 - ## Session log        + 1 row  (<date>, <type>, <scenario/context>, <errors/100w>)
 - ## Recurring errors    merge N categories (M new, K count-bumped)
 - ## Phrasebook          + <n> new say-this-not-that lines (work/casual)
 - ## Listening           + 1 miss-log row      ← only if step 6 ran
 - ## Current focus       refreshed from top recurring categories
─────────────────────────────────────────────────────────────────────────
⚠️  knowledge/language/ is PRIVATE (self-assessed weaknesses tied to
    recruitment) — stays on this machine. MVP exception: may enter the
    Claude API context window (see IMPLEMENTATION.md § "Privacy in the
    Claude-API MVP").
─────────────────────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → step 8.
- **n** → discard, stop. Nothing written.
- **edit** → let the user adjust categories/entries, re-show, ask again.

### 8. Write

If `$BRAIN/knowledge/language/english.md` doesn't exist, create it:

```markdown
---
date: <now, ISO 8601>
source: manual
privacy: private
status: active
tags: [language, english, learning, speaking, listening]
title: "English — practice log & focus"
---

# English — practice log & focus

> Żywy dokument. `/english-review` updates it after each session/call;
> `/english-prep` reads it before one. Bump `date:` on every write.

## Current focus
- <top weak category 1 — concrete focus>
- <top weak category 2>

## Recurring errors
| Kategoria | Count | Last seen | Example | Fix |
|---|---|---|---|---|

## Phrasebook
### Work
- <say-this> — not <not-this>

### Casual
- <say-this> — not <not-this>

## Listening
> Misses from real calls — cause, not just symptom.

| Date | Context | Cause | What was missed | Repair used / should've used |
|---|---|---|---|---|

## Session log
| Date | Type | Scenario/context | Errors/100 words | Top category |
|---|---|---|---|---|
```

Then apply the writes:
- **Recurring errors** — for each category in this session's findings: if the
  category row exists, increment `Count`, bump `Last seen`, optionally replace
  `Example`/`Fix` if this session's instance is clearer. If new, append a row.
- **Phrasebook** — append new say-this/not-this lines under the right
  `### Work` / `### Casual` subsection; skip duplicates (compare case-insensitively).
- **Listening** — append the miss-log row from step 6, if it ran.
- **Session log** — append one row for this session (debrief mode: `type = real call`,
  `errors/100 words = —`).
- **Current focus** — recompute from the top 3-5 `Recurring errors` rows by count
  (ties broken by most recent). Rewrite the whole bullet list — this section is a
  derived summary, not append-only.
- Bump the file's `date:` to now.

### 9. Report

```
── /english-review complete ──────────────────────────────────────────────
✅ knowledge/language/english.md   updated
   Session log:      +1 row (<date>, <type>)
   Recurring errors:  <n> categories touched (<m> new)
   Phrasebook:        +<n> lines
   Listening:          +1 miss (only if step 6 ran)
   Current focus:      refreshed
────────────────────────────────────────────────────────────────────────
💡 To archive the raw transcript verbatim, drop it in
   data_providers/chats/incoming/ and run /ingest-conversation — that's the
   canonical, immutable transcript store; this skill only extracts signal.
────────────────────────────────────────────────────────────────────────
```
