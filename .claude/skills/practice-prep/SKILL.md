---
name: practice-prep
description: >-
  Read-only: generate a paste-ready evaluator prompt for a practice
  conversation with another assistant (Gemini Live or similar) — how to judge
  and summarize, personalized with recorded weak spots from brain/ (career
  records; English log for English sessions). The user writes the role and
  goal; this supplies only evaluation and summary. Use before a mock
  interview, an explain-to-a-junior or explain-to-business drill, any role-play
  practice on a topic being learned, or when asked for a practice/starter
  prompt for Gemini or to prepare a sparring session.
---

# practice-prep

The read half of the practice loop — `/practice-review` writes the session
record, this skill reads the history and turns it into evaluation instructions
for the sparring partner. Exists because an unprompted assistant defaults to
praise: it tends to approve answers that contain factual errors, and only
starts catching mistakes once explicitly told to evaluate critically.

**Scope split:** the user writes the role and goal (who the assistant plays,
what the scenario is). This skill writes **how to evaluate** and **how to
summarize** — never the role, never the scenario.

**Writes nothing.** No confirmation gate.

## When to use

- Before a mock interview, explain-to-a-junior drill, explain-to-business
  drill, or any role-play practice with Gemini Live or a similar assistant.
- When picking up a topic from a previous session's review list.

For pure English-fluency drilling use `/english-prep` — this skill targets
content and communication; it only borrows the top English weak spots when
the session is held in English.

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist, or `BRAIN_PATH` is unset: tell the user to copy
`.claude/gandalf.env.example` to `.claude/gandalf.env` and set `BRAIN_PATH`,
stop. Resolve `$BRAIN`; if it doesn't exist, tell the user to run
`/init-brain` first, stop.

### 2. Gather the input

- `/practice-prep <text>` — the text is the user's description of the session:
  role, goal, topic(s), possibly already the full role prompt they intend to use.
- `/practice-prep` (no argument) — ask once, in the user's chat language:
  "What topic, and who is the counterpart (junior / business / recruiter /
  other)? You can paste the full role and goal."

From the input derive:
- **Topics** — concrete subjects (e.g. `dependency injection`, `StateFlow`,
  `REST idempotency`). If none can be derived, ask for them; don't guess.
- **Audience** — `junior` (explaining down), `business` (PO/PM, non-technical),
  `recruiter` (interview, being questioned), or `other`. Default: `recruiter`
  if the input mentions an interview or mock, otherwise ask.
- **Session language** — the language the practice conversation will be held
  in; default to the user's chat language unless stated otherwise.

If the user hasn't picked topics and asks what is worth practicing, propose 2–3
from step 3's sources (open review items first, then the lowest skills-matrix
levels in their stated area) and let them choose.

### 3. Read the history

Read only what exists; skip missing files silently.

1. `$BRAIN/knowledge/career/mock-interviews/*.md` — the 3 most recent files by
   filename timestamp. Collect:
   - unchecked `- [ ]` items under `## To review` (older records may use a
     localized heading — accept any final checklist section) matching the topics,
   - `## Scores` rows ≤ 3 for matching topics, with their notes,
   - the `**Structural:**` block (thesis-first, fillers, register) — always,
     regardless of topic; these are cross-cutting habits.
2. `$BRAIN/knowledge/career/skills-matrix.md` — rows matching the topics
   (grep topic keywords, read the enclosing section). Always read the
   soft-skills / communication section, whichever number it has.
3. `$BRAIN/knowledge/career/interview-log.md` — any cross-cutting diagnosis
   (recurring patterns across interviews) and any section mentioning the topics.
4. English session only: `$BRAIN/knowledge/language/english.md` → `## Current focus`,
   top 3 rows of `## Recurring errors`.

Topic outside career (e.g. finance, a hobby): career files won't match —
use only the cross-cutting structural habits and say that the topic has no
history yet.

### 4. Build the watch-list

Pick **at most 8** points the evaluator must actively watch for. Each point
must be backed by something read in step 3 — never invent weaknesses. Mix:
- **Topic-specific** (from open review items / low scores / matrix notes),
  phrased as a concrete check ("does the user explain when dependencies are
  resolved"), not a vague area ("knowledge of DI").
- **Cross-cutting** (from Structural / interview-log / soft-skills section):
  thesis-first, precision of terms, filler words, register, defending a
  trade-off under pushback.
- **Audience-specific:**
  - `business` → impact on the user first, then cost/risk/estimate to release,
    no jargon, appropriate register.
  - `junior` → one clear mental model or analogy before details; correctness
    over completeness.
  - `recruiter` → follow-up depth (edge cases, "what if"), an honest "I don't
    know" plus derivation from what is known instead of bluffing.

Never put the user's expected answers or known corrections into the prompt —
the evaluator must check, not be told what the right answer is. Naming the
*area* to probe is fine ("ask about surviving process death"); giving the
answer is not.

**Privacy — the prompt leaves this machine.** The paste-ready block goes to an
external assistant, while its sources are `privacy: private` files. Phrase
every watch-list point as a topic or a habit only. Never include company
names, people, interview outcomes, dates, levels/scores, salary or offer
details, or quotes from the source files. Source references stay in the
step 5 brief, which is shown only in this session.

### 5. Emit the brief

In the user's chat language:

```
── practice-prep ─────────────────────────────────────────────────────────
Topic: <topics>   Counterpart: <audience>   Language: <session language>
Watch-list (<n>):
 - <point> ← <source file + section>
 - ...
No history for: <topics with no data, or "—">
────────────────────────────────────────────────────────────────────────
```

### 6. Emit the paste-ready prompt

One fenced block, to paste **below** the user's own role/goal text. Render it
in the **session language** — translate the template below when the session
is not in English, keeping the section structure identical.

```
## How to evaluate
- Evaluate critically. Don't praise or agree without a concrete reason.
  "Good" without a justification is useless.
- Point out a factual error immediately, in one sentence, with the correct
  version — then return to the role.
- The conversation is spoken and transcribed. If a term sounds garbled by the
  transcription, ask what I meant instead of assuming an error.
- Probe like <audience-specific: an interviewer at my target level / a junior who
  doesn't get it yet / a PO asking about cost and risk>: edge cases,
  "what if", trade-offs. If I back off under pressure, note it.
- Watch closely for:
  - <watch-list point 1>
  - <...>

## Summary
When I say "summarize" or "end", reply in exactly this format:

### Scores
| Topic | Score 1–5 | Justification |

### Factual errors
- What I said → what it should be

### What was missing
- Important points I didn't cover

### Communication
- Structure (did I lead with the thesis), fillers, register, confidence

### To review
- 3 concrete items
```

English sessions: add the English points from step 3.4 under "Watch closely
for", plus: "Flag any misused technical term even if fluency is fine."

The summary format is fixed — `/practice-review` expects these sections to
compare the assistant's own verdict against an independent review.

### 7. Close

One line: after the session, run `/practice-review` with the transcript (the
full `Me:` / assistant exchange, including the assistant's summary).
