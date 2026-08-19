---
name: english-prep
description: >-
  Read-only briefing before an English-practice session or a real English
  call — surfaces the current top weak spots and phrasebook lines from
  brain/knowledge/language/english.md, picks or seeds a practice scenario
  from brain/knowledge/language/english-scenarios.md, and (for a real call)
  produces an audio checklist and repair phrases. Writes nothing. Use this
  skill before starting a Gemini Live conversation-practice session, before
  a real work call conducted in English, or whenever picking up English
  practice and wanting it targeted at actual recurring mistakes instead of
  generic drilling.
---

# english-prep

The read half of the English practice loop — `/english-review` writes the log,
this skill reads it. Produces a short briefing so practice targets real recurring
errors instead of starting cold each time, plus a paste-ready session prompt for
whatever conversational assistant is being used (Gemini Live or similar).

**Writes nothing.** No confirmation gate — there's nothing to gate.

## When to use

- Before a Gemini Live (or similar) English conversation-practice session.
- Before a real work call in English, especially with a non-native-English
  counterpart or over an uncertain connection.
- Any time picking up English practice and wanting it aimed at actual weak
  spots rather than a random topic.

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist, or `BRAIN_PATH` is unset: tell the user to set it
(same messages as `/english-review` step 1), stop.

Resolve `$BRAIN`. If it doesn't exist, tell the user to run `/init-brain` first,
stop.

If `$BRAIN/knowledge/language/english.md` does not exist:
- Say so — no error log exists yet, this will be a generic first session — and
  suggest running `/english-review` on a past transcript first if one exists,
  or just proceed with a starter scenario (skip to step 3 with no focus data).

### 2. Read the current state

Read `$BRAIN/knowledge/language/english.md`:
- `## Current focus` — the top weak spots, already prioritized.
- `## Recurring errors` — pull the top 3-5 rows by `Count` (in case `Current focus`
  is stale relative to the table — prefer the table if they disagree, and mention
  the mismatch).
- `## Phrasebook` — grab 2-3 relevant say-this/not-this lines per weak category,
  split by `Rejestr` (work/casual) if the session type calls for one register.
- `## Listening` — any open pattern (e.g. recurring cause = "accent" or
  "audio quality") worth calling out for a real call.

### 3. Pick or seed a scenario

If `$BRAIN/knowledge/language/english-scenarios.md` doesn't exist yet, create it
with a small starter bank (see step 3a template) — this is a living scenario
library, not a one-off.

- Argument given (e.g. `/english-prep code review`) → match against scenario
  titles/tags in the bank; if none matches, propose adding a new one inline
  (ask, don't just write it — this file has no separate gate here since prep
  itself doesn't write, but flag that adding it belongs to a future
  `/english-review` or manual edit).
- No argument → suggest 1-2 scenarios whose tags best exercise the current top
  weak categories from step 2 (e.g. `tech-vocab` + `passive` → an architecture
  walkthrough scenario).
- Real-call prep (user says "mam za chwilę rozmowę z X") → skip scenario
  selection, go straight to step 5 (pre-call card) using X's context if given
  (e.g. non-native counterpart → emphasize listening).

#### 3a. Starter scenario bank (used only if the file needs creating)

```markdown
---
date: <now, ISO 8601>
source: manual
privacy: private
status: active
tags: [language, english, learning, scenarios]
title: "English — practice scenarios"
---

# English — practice scenarios

> Żywy bank scenariuszy do sesji konwersacyjnych. Dodawaj nowe wg potrzeby —
> tag każdego scenariusza kategoriami błędów, które dobrze ćwiczy.

## Work

### Architecture walkthrough
Tags: tech-vocab, passive, tense
Explain a system you built (layers, data flow, a specific technical decision)
to someone unfamiliar with the codebase, as if onboarding them.

### Code review pushback
Tags: false-friends, word-order, restarts
Disagree with a review comment and propose an alternative approach — defend a
technical trade-off without becoming defensive.

### Standup / status update
Tags: tense, prepositions
Summarize what you did yesterday, what's planned today, and one blocker —
concise, past/future tense mixed naturally.

### Incident retro
Tags: passive, relative-pronouns, tech-vocab
Walk through what went wrong, why, and what changes to prevent recurrence.

## Casual

### Small talk at the desk
Tags: false-friends, polish-filler
Weekend, weather, a show you're watching — no technical vocabulary allowed.

### Explaining a hobby
Tags: word-order, articles
Describe a hobby or recent trip to someone who's never heard of it.
```

### 4. Emit the focus brief

```
── English prep ──────────────────────────────────────────────────────────
Top weak spots (from <n> sessions logged):
 1. <category> — <count>× — <one concrete say-this-not-that example>
 2. <category> — <count>× — <example>
 3. <category> — <count>× — <example>

Scenario: <title> (tags: <tags>)
<one-line scenario description>
────────────────────────────────────────────────────────────────────────
```

### 5. Emit the paste-ready session prompt

```
You're helping me practice spoken English. Scenario: <scenario description>.

Please specifically watch for these patterns I tend to repeat, and correct
me on them even if you'd otherwise let them pass:
- <category 1>: <what to watch for, from the phrasebook>
- <category 2>: <...>
- <category 3>: <...>

Also flag any misused technical/domain term, even if it doesn't affect
overall fluency — I'd rather sound slightly awkward than say the wrong
term confidently.

Keep the conversation going naturally; save corrections for the end unless
something would cause a real misunderstanding.
```

Fill in the categories/examples from step 2 — never invent ones not backed by
the log.

### 6. Pre-call card (real-call prep only)

```
── Pre-call checklist ────────────────────────────────────────────────────
Audio:
 - [ ] Your mic/headset tested, not laptop mic
 - [ ] If recurring issue with this counterpart's audio: ask them to switch
       device/headset before starting, not mid-call
Repair phrases (use these — asking twice costs nothing):
 - "Sorry, you're breaking up — could you repeat the last part?"
 - "Let me make sure I got that: you're saying <X>?"
 - "Could you drop that in the chat?"
Habit: restate the key point back before responding to it — turns a
comprehension gap into a normal clarification, not a stall.
────────────────────────────────────────────────────────────────────────
```

Only include this block for real-call prep, not drill sessions — drills don't
need an audio checklist.
