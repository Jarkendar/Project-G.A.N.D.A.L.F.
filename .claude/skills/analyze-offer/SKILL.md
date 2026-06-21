---
name: analyze-offer
description: >-
  Generate or update a structured job offer dossier in
  brain/knowledge/career/offers/ — offer analysis, skill fit, learning
  checklist, recruiter questions, the user's own questions, business/product
  research, and a summary of everything brain/ already knows about the
  company. Use this skill before applying (research company/stack/fit, build
  the learning checklist), before an interview (review the dossier, add prep
  notes), after an interview (update stage, log outcomes/feedback), or to
  update a stale dossier — the skill detects an existing file and offers an
  in-place update.
---

# analyze-offer

Generate or update a structured job offer dossier for a single offer.
Stores one file per offer in `brain/knowledge/career/offers/` — a living document
covering offer analysis, skill fit, learning checklist, recruiter questions, your
own questions, business/product research, and a summary of everything `brain/`
already knows about the company.

## When to use

- Before applying: research the company, stack, and fit; build the learning checklist.
- Before an interview: review the dossier, check the learning checklist, add prep notes.
- After an interview: update Stage, append a dated log entry with outcomes and feedback.
- Updating a stale dossier: the skill detects an existing file and offers in-place update.

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

Check that `$BRAIN/knowledge/` exists. If missing, tell the user to run `/init-brain`
(validation mode) and stop.

### 2. Determine the offer input

The skill can be invoked with one of three input forms:

**(a) URL** — if the argument looks like a URL, fetch it with WebFetch. Extract:
company name, role title, seniority, stack, requirements, contract type, work mode.

**(b) Pasted text** — if the argument is a block of job posting text (no URL),
parse it directly.

**(c) Company/role name only** (e.g. `/analyze-offer Allegro Android mid`) — use
web search to find a relevant current posting; confirm with the user before proceeding.

If no argument is given, ask:
> "Provide the offer: paste the job description, a URL, or just the company and role name."

### 3. Derive the slug and target path

`<slug>` = `<company>-<role-keywords>` in lowercase kebab-case, max 50 chars, no
special characters. Strip common stop words (e.g. "developer", "engineer" can be
shortened). Examples:
- Capgemini DCX · Android Developer (mid) → `capgemini-dcx-android-mid`
- LUX MED · Android Developer → `lux-med-android`
- Collinson Group · Android Developer → `collinson-group-android`

Target path: `$BRAIN/knowledge/career/offers/<slug>.md`

### 4. Existing dossier check

If the target file already exists:
- Read it and show the current Stage and date.
- Ask: "Dossier for `<slug>` already exists (Stage: `<stage>`, updated: `<date>`).
  Update in place? [y = update  |  n = abort  |  new = create a second file with suffix]"
- On `y`: proceed in **update mode** — preserve all existing sections; only extend
  or revise content; append a new dated entry to `## Log`; bump `date:` frontmatter.
- On `n`: stop.
- On `new`: append `-2` (or next available suffix) to the slug and continue as new.

### 5. Web research (default ON)

Perform two targeted searches unless the user explicitly passed `--no-web`:

**(a) Company / product research:**
Search for: `<company name> company product description 2025 OR 2026`
Goal: understand what the company does, its business model, key products, user scale,
tech stack publicly known. Use WebSearch + WebFetch on top 1–2 results.

**(b) Recruiter questions research:**
Search for: `<company name> Android interview questions site:glassdoor.com OR teamblind.com OR levels.fyi`
If company-specific results are sparse, fall back to: `Android Developer mid interview questions <stack keywords>`
Goal: identify recurring technical and behavioural questions asked at this company
(or for this stack level).

Summarise findings; do not quote copyrighted content verbatim — paraphrase and cite
the source URL.

The user can suppress web research for a single run by invoking as
`/analyze-offer --no-web <offer>`.

### 6. Scan brain/ for company knowledge

Search `brain/` for any existing information about this company:

```bash
grep -ri "<company name>" "$BRAIN/knowledge/career/interview-log.md" 2>/dev/null
grep -ri "<company name>" "$BRAIN/current/context/job-search.md" 2>/dev/null
find "$BRAIN/knowledge/career/offers/" -name "*<company-slug>*" 2>/dev/null
grep -ri "<company name>" "$BRAIN/knowledge/" 2>/dev/null | grep -v "offers/"
```

Collect all matches. This feeds **Section 7** of the dossier (the mandatory "what
brain/ already knows" block).

If no matches: note "No prior data about this company in brain/."

### 7. Cross-reference skills-matrix.md

Read `$BRAIN/knowledge/career/skills-matrix.md` (if it exists).

For each **must-have** requirement in the offer:
- Map it to the closest area/row in the matrix.
- Record the current level (A / B / C / X).
- Flag C and X levels as items for the learning checklist (Section 3).

If `skills-matrix.md` does not exist, note it in Section 3 and skip the cross-ref.

### 8. Synthesise the dossier

Compose the full document using the structure below. Do not invent facts — every
claim must come from the offer text, web research, brain/ scan, or skills-matrix.

---

#### Dossier structure

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: analyze-offer
privacy: private
status: active
tags: [career, offer, <company-slug>, android, job-search]
title: "<Company> — <Role> (<Seniority>)"
---

# <Company> — <Role> (<Seniority>)

| Field | Value |
|---|---|
| Company | <name> |
| Role | <title> |
| Seniority | <level> |
| Source | <URL or "pasted text" or "web search"> |
| Analysed | <YYYY-MM-DD> |
| Stage | `researching` |
| Decision | `waiting` |

---

## 1. Offer analysis

### Stack
<bullet list of technologies and versions from the offer>

### Requirements
**Must-have:**
- <item>

**Nice-to-have:**
- <item>

### Contract & logistics
- Type: <B2B / UoP / EOR / unknown>
- Work mode: <remote / hybrid / on-site; days if specified>
- Location: <city or remote>
- Salary range: <if stated>

### Red flags vs my profile
<any mismatch with deal-breakers from profile.md — loud open space, micromanagement
signals, no remote, products-into-a-drawer, etc. If none: "None identified.">

---

## 2. Fit assessment

| Requirement | My level | Notes |
|---|---|---|
| <requirement> | <A/B/C/X> | <from skills-matrix> |

**Overall fit:** <brief paragraph — where strong, where gaps>

---

## 3. Learning checklist

> Items derived from C/X gaps in Section 2. Check off as you study.

- [ ] <topic> — <why needed for this offer; reference to skills-matrix area>
- [ ] …

*Tip: cross-reference with `interview-log.md` for what this or similar companies asked.*

---

## 4. Probable recruiter questions

> Sources: web research + patterns from interview-log.md.

### Technical
- **<question>** — *Prep note: <what to cover / which story to use>*

### Behavioural / situational
- **<question>** — *Prep note: <STAR angle>*

### Architecture / system design
- **<question>** — *Prep note: <framework to apply>*

---

## 5. My questions for them

### Contract & role
- <question>

### Team & product
- <question>

### Process & culture
- <question>

### Growth
- <question>

---

## 6. Business & product analysis

> Source: web research (<URL(s) used>).

<2–4 paragraphs covering: what the company does, business model, key products,
user base / scale, tech stack publicly known, market position, recent news if relevant>

---

## 7. What brain/ already knows about this company

> Source: grep scan of brain/ — interview-log.md, job-search.md, prior dossiers.

<Paste relevant excerpts or summaries. Keep attribution (file + section).
If nothing found: "No prior data about this company in brain/.">

---

## Log

> Append-only. Add a dated entry after each meaningful event.

- <YYYY-MM-DD> — Dossier created.
```

---

### 9. Privacy gate — confirm before writing

Before writing, show the user:

```
── Proposed write ───────────────────────────────────────
File:    <full path>
Mode:    <new file | update in place>
Privacy: private
──────────────────────────────────────────────────────────
⚠️  knowledge/career/offers/ content is PRIVATE and stays on this
    machine. In the MVP it may enter the Claude API context window
    (see IMPLEMENTATION.md § "Privacy in the Claude-API MVP").
    Tightened in Phase 2.
──────────────────────────────────────────────────────────
Change summary:
<short description: sections written, web sources used, brain/ hits found>
──────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write (step 10).
- **n** → discard, stop.
- **edit** → let the user correct content, re-show and ask again.

### 10. Write

Create `$BRAIN/knowledge/career/offers/` if it does not exist.

Write the dossier file at the target path.

**New file:** write the full document as synthesised in step 8.

**Update mode:** read the existing file; merge new findings into each section;
append a new dated entry to `## Log`; bump `date:` frontmatter to current datetime.
Preserve all existing content — do not overwrite Log entries or checked checklist items.

### 11. Report

```
── Dossier complete ─────────────────────────────────────
✅ Written:  <full path>
   Mode:     <new | updated>
   Stage:    <current stage>
   Sections: <list of sections written/updated>
   date:     <new value>
   Privacy:  private
─────────────────────────────────────────────────────────
Next: update Stage when you apply / schedule an interview.
      Use `/analyze-offer <slug>` again to add prep notes before the call.
```

---

## Stage lifecycle

Update the `Stage:` field in the header table as the process moves:

| Stage | When |
|---|---|
| `researching` | Dossier just created; not yet applied |
| `ready` | Applied or decided to apply; dossier prep complete |
| `interview-scheduled` | Interview booked |
| `interviewed` | Interview done; awaiting outcome |
| `closed-won` | Offer accepted |
| `closed-lost` | Rejected by the company, withdrawn, **or user decided not to apply** |

To update Stage: re-run `/analyze-offer <slug>` (update mode) and edit the header
table, or edit the file manually.

**Archiving:** when Stage reaches `closed-won` or `closed-lost`, set frontmatter
`status: archived`. T.R.E.E.B.E.A.R.D. will move the file to `archive/` in its next
sweep. Do not delete dossiers — follow the append-only + supersession convention.

### Compact mode — user decides not to apply

When the user reports they will **not** apply to an offer that already has a
dossier (Stage `researching`), do not leave the full 7-section dossier in place.
Compact it on the same update pass:

1. Set `Stage: closed-lost`, `Decision: not-applying`, bump `date:`.
2. Collapse Sections 1–6 (offer analysis, fit, learning checklist, recruiter
   questions, my questions, business analysis) into a single short paragraph
   under a `## Summary` heading — 2–4 sentences max: what the offer was, why
   skipped (deal-breaker, comp, stack mismatch, timing, etc.), anything worth
   remembering if this company resurfaces.
3. Keep **Section 7** ("what brain/ already knows") only if it found prior
   data — otherwise drop it.
4. Keep `## Log` as-is and append the compaction entry, e.g.
   `<date> — Not applying (<short reason>). Dossier compacted.`
5. Confirm the compaction in the privacy gate (step 9) same as any other write
   — show a diff-style summary, not the full new file, since it's a trim.

Goal: the dossier stays useful for future brain/ scans (dedup, "have we seen
this company before") without carrying dead weight from an offer that was
never pursued.

---

## Notes

- **One file per offer.** Do not merge multiple offers into one dossier.
- **Living document, not append-only** (except `## Log` which is always append-only).
  Edit sections in place as knowledge grows.
- **No invented facts.** Business analysis from web research only; fit assessment from
  `skills-matrix.md` only; company history from `brain/` grep only.
- **Web research is default ON.** Pass `--no-web` to skip. The user can also ask to
  skip web mid-session.
- **Does not touch `_meta/`.** `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory.
- **Privacy:** `privacy: private` is always set. Dossiers combine personal fit
  assessment with company analysis — both halves are sensitive.
- **brain/ scan scope:** reads `interview-log.md`, `job-search.md`, and existing
  `offers/` files. Does not read `core/` content and relay it to external APIs
  (MVP exception applies — see IMPLEMENTATION.md).
