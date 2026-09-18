---
name: practice-review
description: >-
  Independently review the transcript of a practice conversation (mock
  interview, explain-to-a-junior or explain-to-business drill with Gemini
  Live or similar) — score each topic, list factual errors including the
  ones the sparring assistant missed or accepted, assess communication
  structure, and save the result as a session record in
  brain/knowledge/career/mock-interviews/, optionally with gated notes in
  skills-matrix.md. Use this skill right after a practice session, when the
  user pastes a Me:/assistant transcript and asks to evaluate it, asks what
  to improve, or asks to save something from it, or to close the loop
  started by /practice-prep.
---

# practice-review

The write half of the practice loop — `/practice-prep` reads what this skill
writes. The sparring assistant's own verdict is **input, not ground truth**:
assistants grading live conversations miss domain errors and drift into praise.
This skill re-checks every claim the user made.

Distinct from `/english-review` (language errors in English sessions) and
`/ingest-conversation` (verbatim archive). This skill extracts content and
communication signal only.

## When to use

- Right after a practice session run with a `/practice-prep` prompt.
- When the user pastes any practice transcript and asks for an assessment.

---

## Steps

### 1. Resolve BRAIN_PATH

Same as `/practice-prep` step 1. Target folder:
`$BRAIN/knowledge/career/mock-interviews/`. If it doesn't exist, offer to
create it; proceed only after confirmation.

Non-career topic (finance, hobby, …): propose `$BRAIN/knowledge/<domain>/practice/`
instead and ask before creating it.

### 2. Gather the input

- `/practice-review <pasted text>` or `<path>` (read the file).
- No argument → ask, in the user's chat language, for the transcript
  (`Me:` / assistant labels).

Multiple sessions pasted together → one record, each session listed in the
header table; topics scored separately.

Session held in English → review content here, and at the end suggest
`/english-review` on the same transcript for language errors. Don't do both
analyses in one skill.

### 3. Read context

- The 3 most recent files in the target folder — to spot repeated problems
  (e.g. the same structural habit flagged again) and to know the record format.
- `skills-matrix.md` rows for the topics — current level, so the review can say
  whether the session confirms or contradicts it.

### 4. Review

Analyse **only `Me:` lines as the user's performance**; assistant lines are
context and a second object of review (step 4.5).

1. **Topics** — list every topic actually discussed, in order.
2. **Factual check** — for each substantive claim: correct / imprecise / wrong.
   Correct wrong and imprecise ones in one or two sentences with the right
   version. Include omissions an interviewer at the user's target level would
   expect (e.g. a DI-and-testing answer that never mentions constructor
   injection making unit tests framework-free).
3. **Transcription artifacts** — speech-to-text garbles of a correct term are
   not errors. Only flag a term if the user repeated it consistently or the
   context shows a real misconception. When unsure, list it as a question,
   not an error.
4. **Communication:**
   - thesis-first, or detail-first?
   - structure: thesis → reasoning → example → trade-off
   - filler words and hedges — note if they weaken the message, don't count
     them obsessively
   - register — especially in business-audience parts
   - business-audience parts: user impact first, cost/risk, estimate to
     release (not to commit), no jargon
   - pushback: held the position with a trade-off, or backed off?
5. **Sparring partner quality** — did the assistant catch the errors from 4.2?
   Did it praise wrong answers? Did it follow the `/practice-prep` summary format?
   One short paragraph; this tells the user how much to trust future sessions.
6. **Scores** — 1–5 per topic, with one-line notes. Calibrate against the
   target level recorded in `skills-matrix.md` (or stated in the session goal).
   Scores are your own, not the assistant's; mention where they differ materially.
7. **To review** — 3–5 concrete, checkable items, each phrased as something
   to be able to *say*, not "read about X".

### 5. Present

Show the review in chat, in the user's chat language, concisely —
highest-impact errors first. Then build the write plan.

### 6. Write plan

```
── practice-review — proposed update ─────────────────────────────────────
New:    knowledge/career/mock-interviews/<YYYY-MM-DDTHH-MM-SS>_<slug>.md
Edit:   knowledge/career/skills-matrix.md          ← only if proposed below
         § <N> "<row>": append a dated update note + link to the new record
─────────────────────────────────────────────────────────────────────────
⚠️  PRIVATE (self-assessed weaknesses tied to recruitment). MVP exception:
    may enter the Claude API context window (IMPLEMENTATION.md § "Privacy in
    the Claude-API MVP").
─────────────────────────────────────────────────────────────────────────
Write this? [y / n / edit]   (skills-matrix edits can be accepted separately)
```

**skills-matrix rules** — it is an owner-authored living document:
- Propose a note only when the session adds real signal to an existing row
  (confirms a gap, shows progress, contradicts the level).
- Append to the row's note, matching the language and dated-update style
  already used in that document. Never rewrite existing note text.
- **Never change the level column** unless the user explicitly asks — one
  practice session is not enough evidence.
- Show the exact before/after row. Each row edit is accepted individually.
- Bump the file's `date:` only if a row was edited.

Previous session records are **not** edited (no ticking old review items).
If this session demonstrates a previous item, say so in the new record's
`## To review` section ("✅ from <file>: …").

### 7. Write

Record format — section headings in English so `/practice-prep` can parse
them; body text in the user's chat language:

```markdown
---
date: <now, ISO 8601>
source: mock-interview (<assistant>, <voice/text>; reviewed by Claude)
privacy: private
status: active
tags: [career, mock-interview, <audience>, <topic tags>]
title: "Mock — <short description> (<assistant>) — <YYYY-MM-DD>"
---

# Mock — <short description> (<YYYY-MM-DD>)

| Field | Value |
|---|---|
| Mode | <role-play description> |
| Tool | <assistant, voice/text> |
| Sessions | <n> (<topics per session>) |
| Reviewed | Claude, <YYYY-MM-DD> |

---

## Scores

| Topic | Score (1–5) | Notes |
|---|---|---|

**Structural:**
- Thesis-first: <used / partial / not used — where>
- <other cross-cutting observation>

---

## Factual corrections
1. **<claim>** — <correct version>

## <Audience-specific section, e.g. "Business version — what to add">   ← only if applicable

## <Assistant> as sparring partner
<paragraph from step 4.5>

## To review
- [ ] <item>
```

Filename slug: kebab-case, 3–5 words describing the format and topic
(e.g. `explain-to-junior-gemini`, `business-state-loss`).

### 8. Report

```
── /practice-review complete ─────────────────────────────────────────────
✅ mock-interviews/<file>   created (<n> topics, avg <x>/5)
✅ skills-matrix.md          <n> row notes appended   (or: unchanged)
────────────────────────────────────────────────────────────────────────
Next session: /practice-prep <top "To review" topic>
English session? → /english-review on the same transcript.
```

No commit — the user commits `brain/` themselves or asks for it.
