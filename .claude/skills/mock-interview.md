# mock-interview

Run an adaptive mock interview (technical, behavioural, or system design) calibrated
from the existing career KB in `brain/`. Asks one question at a time, gives per-answer
structural + merit feedback, scores the session per topic, and writes a result file to
`brain/knowledge/career/mock-interviews/` for trend analysis.

The questions are generated from context at runtime — never hardcoded. The session
trains the specific failure pattern identified in `interview-log.md`: building answers
live under pressure instead of using prepared structures.

## When to use

- Practising for an upcoming interview (pass the offer slug to target its stack)
- Closing a specific gap (pass a topic keyword: `coroutines`, `hilt`, `behavioral`)
- Regular unguided practice (no argument — skill picks the highest-priority gaps)
- Reviewing which topics are still red just before an interview

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
Call it `$BRAIN`. If `$BRAIN` does not exist on disk:
- Tell the user to run `/init-brain` first.
- Stop.

### 2. Parse arguments

The skill accepts zero or more arguments in any order:

**Offer slug** — a string matching an existing file under
`$BRAIN/knowledge/career/offers/<slug>.md`. If matched, read the dossier.
Offer-targeted mode: questions are weighted toward the offer's must-have requirements.

**Topic keyword** — a free-form word or phrase (e.g. `coroutines`, `system-design`,
`behavioral`, `hilt`, `oauth2`, `rest`). Sets the primary focus area. Multiple keywords
may be given (comma-separated or space-separated).

**Mode flags** (optional, case-insensitive):
- `--tech` — technical questions only (Kotlin, architecture, libraries, testing)
- `--behavioral` — behavioural / situational questions only (STAR format)
- `--design` — system design questions only
- `--mixed` — all three types, interleaved (default if no flag is given)

**No argument** — open practice mode. Skill selects focus from the highest-priority
gaps (X/C levels in `skills-matrix.md` weighted by recurrence in `interview-log.md`).

Record the resolved `$OFFER_SLUG`, `$FOCUS_KEYWORDS`, `$MODE` for later steps.

### 3. Load KB context

Read the following files. They are all `privacy: private` — the MVP exception applies
(content may enter the Claude API context window per IMPLEMENTATION.md §
"Privacy in the Claude-API MVP"). Do not relay their contents to any external service
other than the Claude API engine.

**Always read:**
- `$BRAIN/knowledge/career/skills-matrix.md` — competency levels (A/B/C/X) per area;
  drives question difficulty and focus selection.
- `$BRAIN/knowledge/career/gap-plan.md` — active study plan; drives recommendations.
- `$BRAIN/knowledge/career/interview-log.md` — real questions asked by past companies,
  and the cross-cutting failure diagnosis.
- `$BRAIN/core/identity/profile.md` — personal facts to anchor questions in real
  experience (Emapa, State Machine, SDK integration models, Dagger→Koin, Android Auto).

**If stories.md is non-empty (not all `<!-- TODO -->`):**
- `$BRAIN/knowledge/career/stories.md` — available STAR stories to suggest during
  behavioural questions. If the file is still a skeleton, note it and continue without.

**If offer slug provided:**
- `$BRAIN/knowledge/career/offers/<slug>.md` — must-have requirements, stack, fit
  assessment, and any existing recruiter questions from the dossier.

If any file does not exist, note it in the session header and continue without it.

### 4. Determine focus and session plan

Using the loaded KB, decide what this session will cover.

#### 4a. Focus selection

**If offer slug given:** pick 3–5 must-have requirements from the dossier that have
level C or X in `skills-matrix.md`. Supplement with 1–2 behavioural questions
(always included regardless of mode).

**If topic keywords given:** centre the session on those areas. Check their level in
the matrix; calibrate difficulty accordingly.

**No argument (open practice):** rank areas by priority:
1. Level X in `skills-matrix.md` — genuine gaps.
2. Level C areas that recur in `interview-log.md` — proven weak spots in real interviews.
3. Level C areas currently in Tier 1 or Tier 2 of `gap-plan.md`.

Pick the top 2–3 areas. Always include at least one behavioural question in `--mixed`
or `--behavioral` mode.

#### 4b. Question count

Target **7 questions** by default. The user can change this:
- `--short` → 4 questions
- `--long` → 12 questions
- Any explicit number (e.g. `5`) → that many questions

Do not fix the exact questions now — generate each one contextually as the session
progresses.

#### 4c. Announce the session plan

Print a brief session header before the first question:

```
── Mock Interview ───────────────────────────────────────
Mode:    <tech | behavioral | design | mixed>
Focus:   <area(s) selected>
Offer:   <slug | open practice>
Target:  <n> questions
─────────────────────────────────────────────────────────
Sources loaded: skills-matrix ✅  gap-plan ✅  interview-log ✅
                profile ✅  stories <✅ | ⚠️ empty skeleton>
                offer dossier <✅ | —>
─────────────────────────────────────────────────────────
Ready? [Enter to start  |  s = change settings]
```

On `s`: let the user adjust mode, focus, or question count, then re-show the header.

### 5. Conduct the mock

Ask questions **one at a time**. Wait for the user's full answer before continuing.
Behave like a real recruiter: concise questions, attentive listening, follow-ups.

#### Per question:

**Ask the question.** Label it internally as type T (technical), B (behavioural), or D
(system design). Do not show the label to the user — it is for the session log.

**After the answer:**
1. **Follow-up if needed.** If the answer is vague, partial, or opens an angle worth
   exploring: ask one targeted follow-up. Maximum one follow-up per main question.
   If the answer is complete and clear: skip the follow-up.
2. **Escalate on strength.** If the answer is noticeably strong: the next question on
   the same topic goes one difficulty level up. If weak: the next question on a
   different topic gives some breathing room.
3. **Give feedback** — keep it short, direct, actionable. Two parts:
   - **Structure:** did the answer start with the result (headline-first)? Did it
     follow STAR (for B questions)? Was it concise or rambling?
   - **Merit:** one sentence on technical/domain correctness. Flag any specific error
     (wrong type for money, missing idempotency, private key in SharedPreferences, etc.).
   Do not give long explanations during the session — that breaks the drill. Detailed
   notes go in the session log.
4. **Acknowledge and continue.** One sentence max, then ask the next question.

The user can say "skip", "pass", "next", "enough", or "done" at any point:
- "skip" / "pass" / "next" → move to the next question without feedback.
- "enough" / "done" → end the session immediately, go to step 6.

**Question types and anchoring:**

*Technical (T):*
Generate from the focus area and the user's level in `skills-matrix.md`.
- Level X: foundational "explain / define / compare" questions.
- Level C: application questions ("when would you use X?", "what's wrong with Y?").
- Level B: trade-off / design-decision questions.
Examples of recurring gaps to draw from: `Nothing` type usage, `reified` generics,
`callbackFlow` vs cold Flow, `supervisorJob` vs `coroutineScope`, Hilt vs Koin
scoping, Retrofit vs Ktor, offline-first Repository contract, `@Inject` vs `@Provides`,
`double` for money (red flag from Allegro), encrypted SharedPreferences deprecation,
Android 14+ Foreground Service type declaration, BroadcastReceiver limits API 26+.

*Behavioural (B):*
Always demand STAR format + headline-first. If `stories.md` has a relevant story,
hint before the question: "You have a prepared story on this — consider using it."
Examples of angles: past technical mistake and what you learned; disagreement with a
PO/PM decision; prioritising tech debt under deadline; communicating complexity to
a non-technical stakeholder; changing direction mid-implementation.

*System design (D):*
Real pothole questions derived from `interview-log.md` failures at Allegro and beyond.
Examples: design a shopping cart API (REST vs RPC, idempotency keys, `BigDecimal` for
amounts, OAuth2 + refresh token flow, DataStore encryption), offline-first sync
(conflict resolution, Room + Ktor, network state), pagination strategy (Paging 3 vs
manual), WebSocket / SSE channel design.

### 6. Score the session

After the last question (or when the user ends early), produce the evaluation.

#### Score table

For each topic area covered in the session, assign a score 1–5:

| Score | Meaning |
|---|---|
| 5 | Strong — answer complete, correct, structured, no prompting |
| 4 | Good — minor gap or structure issue, no major errors |
| 3 | Partial — correct concept but incomplete, or structural weakness |
| 2 | Shaky — significant gap, needed follow-up to reach basic coverage |
| 1 | Red — wrong, missing, or could not answer |

Also rate two structural dimensions across the whole session (not per question):

| Dimension | Rating |
|---|---|
| Headline-first | consistent / partial / not used |
| STAR compliance | consistent / partial / not used |

#### Gaps revealed

List specific sub-topics that surfaced as weak during the session (not the broad area —
the specific concept, e.g. "idempotency key placement in POST body", not "REST").

#### Recommendations

Cross-reference the gaps with `gap-plan.md`. For each gap:
- If it is already in the plan → note the tier and current status.
- If it is not in the plan → flag it as a new item to add.

Format as a checkbox list so the user can tick items off.

Print the full evaluation:

```
── Session complete ─────────────────────────────────────
Questions: <n asked> / <n planned>   Mode: <mode>
─────────────────────────────────────────────────────────
Scores
──────
<topic>        <1–5>   <one-line note>
<topic>        <1–5>   <one-line note>
…

Structural
──────────
Headline-first:   <consistent | partial | not used>
STAR compliance:  <consistent | partial | not used>

Gaps revealed
─────────────
- <specific sub-topic>
- …

Recommendations (cross-ref gap-plan)
─────────────────────────────────────
- [ ] <action>  [plan tier: <T1/T2/T3/new>]
- [ ] …
─────────────────────────────────────────────────────────
Save this session to brain/? [y / n]
```

### 7. Privacy gate — confirm before writing

On `y` in step 6, show the write preview:

```
── Proposed write ───────────────────────────────────────
File:    $BRAIN/knowledge/career/mock-interviews/<timestamp>_<focus>.md
Mode:    new file
Privacy: private
──────────────────────────────────────────────────────────
⚠️  knowledge/career/ content is PRIVATE. In the MVP it may enter the
    Claude API context window (IMPLEMENTATION.md § "Privacy in the
    Claude-API MVP"). Tightened in Phase 2.
──────────────────────────────────────────────────────────
Change summary:
Mock interview — <mode>, focus: <areas>, <n> questions, scores: <range>
──────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write (step 8).
- **n** → discard, stop. Nothing written.
- **edit** → let the user adjust the output, re-show the preview, ask again.

### 8. Write

Create `$BRAIN/knowledge/career/mock-interviews/` if it does not exist.

Filename: `YYYY-MM-DDTHH-MM-SS_<focus-slug>.md`
where `<focus-slug>` is a lowercase kebab-case slug of the focus areas (≤30 chars).

Write the result file using this structure:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: mock-interview
privacy: private
status: active
tags: [career, mock-interview, <focus-tag(s)>, android, job-search]
title: "Mock — <Focus> — <YYYY-MM-DD>"
---

# Mock Interview — <Focus> (<YYYY-MM-DD>)

| Field | Value |
|---|---|
| Mode | <tech / behavioral / design / mixed> |
| Focus | <area(s)> |
| Offer | <slug \| open practice> |
| Questions | <n asked> / <n planned> |
| Scored | <YYYY-MM-DDTHH:MM:SS> |

---

## Scores

| Topic | Score (1–5) | Notes |
|---|---|---|
| <topic> | <n> | <note> |

**Structural:**
- Headline-first: <consistent / partial / not used>
- STAR compliance: <consistent / partial / not used>

---

## Session log

### Q1 — <topic> [T/B/D]

**Q:** <exact question asked>

**A (summary):** <concise summary of the answer — key points, not verbatim>

**Feedback:** <structure note> / <merit note>

---

### Q2 …

(repeat for each question)

---

## Gaps revealed

- <specific sub-topic>

---

## Recommendations

> Cross-referenced with gap-plan.md

- [ ] <action>  [plan tier: <T1 / T2 / T3 / new>]
```

This file is **NOT** a living document — it is an immutable session record.
Do not edit it after writing. Future mock sessions create new files. T.R.E.E.B.E.A.R.D.
will archive old sessions; do not delete them.

**v1 scope:** this skill does NOT update `skills-matrix.md` automatically.
At the end of the report, offer a prompt: "Want to update skills-matrix.md based on
these scores? → run `/update-core` or wait for B2 (auto-matrix) to be built."

### 9. Report

```
── Mock saved ───────────────────────────────────────────
✅ Written:  <full path>
   Focus:    <areas>
   Scores:   <weakest area: n>  →  <strongest area: n>
   Privacy:  private
─────────────────────────────────────────────────────────
Next: run again on the same focus to track trend, or
      target a specific offer: /mock-interview <slug>
```

---

## Notes

- **Questions generated at runtime.** No question is hardcoded here. The question set
  is derived from the user's KB (skills-matrix, gap-plan, interview-log, profile) at
  session start. Each session is different.
- **One question at a time.** The fundamental drill is answering under pressure, not
  reading a list. Never batch-show the questions.
- **Feedback is brief during the session.** Long explanations during a mock break the
  training effect. Detailed notes go in the session log, reviewed after.
- **Structural feedback is mandatory.** Headline-first and STAR compliance are always
  evaluated — even on technical questions. This is the diagnosed failure mechanism.
- **stories.md status matters.** If `stories.md` is still a skeleton (`<!-- TODO -->`),
  behavioural questions are still asked, but the skill cannot suggest prepared stories.
  Recommend running `/interview` (Session D) to fill it.
- **Session record is immutable.** After writing, the file is never edited in place.
  Trend analysis reads multiple files in sequence; editing past records breaks the
  series.
- **Does not touch `_meta/`.** `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory.
- **v1 does not auto-update skills-matrix.** Automatic matrix updates (B2 in the
  roadmap) require a human-review gate not yet built. The skill proposes the update
  and defers execution to the user.
- **Privacy:** `privacy: private` is always set on the result file. Session records
  contain personal competency data combined with real question content — both halves
  are sensitive.
