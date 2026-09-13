---
name: develop-idea
description: >-
  Turn one raw personal project idea — pasted text (possibly pre-structured by
  an n8n automation, format not guaranteed) or an existing
  brain/backlog/projects/<slug>.md item — into a researched dossier in
  brain/knowledge/projects/: feasibility assessment, web research on existing
  solutions/prior art, a proposed execution scenario, future expansion ideas,
  and a personalized skill-growth assessment calibrated against
  core/identity/profile.md and goals.md. Use this skill when the user wants to
  properly evaluate a project idea before committing to it, when promoting a
  backlog idea into real planning (supersedes the raw-copy "promote" action in
  `/idea list`), or when the user says "rozwiń pomysł", "rozwiń ten projekt",
  "sprawdź czy to ma sens", "zrób dossier projektu", "obrobiony pomysł do
  brain", or "czy to już ktoś zrobił" about a project idea.
---

# develop-idea

Turn one raw project idea into a researched dossier: feasibility, prior art,
an execution scenario, future expansion, and a personalized skill-growth
assessment. Stores one file per idea in `brain/knowledge/projects/` — a living
document that starts as a dossier and can later track the project's own
lifecycle (planned → in-progress → shipped/abandoned).

This is the richer sibling of `/idea` (raw capture, no research) — it formalises
and supersedes the raw-copy "promote" action in `/idea list` for ideas worth
actually evaluating before starting.

## When to use

- Deciding whether a project idea is worth pursuing before committing time to it.
- Promoting a `backlog/projects/<slug>.md` item into real planning.
- Checking whether something similar already exists ("czy to już ktoś zrobił").
- Updating a stale dossier — the skill detects an existing file and offers an
  in-place update, including moving the project's own Stage forward.

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

Check that `$BRAIN/knowledge/` and `$BRAIN/backlog/` both exist. If either is
missing, tell the user to run `/init-brain` (validation mode) and stop.

### 2. Determine the idea input

The skill can be invoked with one of two input forms:

**(a) Backlog reference** — if the argument matches an existing
`$BRAIN/backlog/projects/<slug>.md` filename exactly, use it directly (Mode B).
Otherwise, fuzzy-match the argument (case-insensitive) against the `title:`
frontmatter of every file in `$BRAIN/backlog/projects/*.md`. Exactly one match →
confirm ("Did you mean `<slug>` — '<title>'?"), then Mode B. Multiple matches →
list them and ask which. No match → treat as raw text (b).

**(b) Raw idea text** — pasted or described text, of any shape. It may be a
terse one-liner, a multi-paragraph note, or already-structured output from the
user's personal n8n automation — no fixed input schema is assumed. Extract
title/summary/context heuristically from whatever arrives (Mode A).

If no argument is given, ask:
> "Paste the idea, or give me a backlog slug or title to develop (e.g. `desktop-brain-viewer`)."

If raw text is terse (fewer than ~15 words), ask one brief follow-up:
> "Any more context — what problem it solves, why now, rough scope?"

If the user declines or it's already clear, proceed with what you have.

### 3. Duplicate-idea check (Mode A only)

Before treating raw text as brand-new, grep for close matches to the idea's
likely title/keywords:

```bash
grep -ril "<keyword>" "$BRAIN/backlog/projects/" "$BRAIN/knowledge/projects/" 2>/dev/null
```

If a plausible existing backlog item turns up, surface it:
> "This looks similar to `backlog/projects/<slug>.md` ('<title>'). Develop that
> instead? [y = use it (switches to Mode B) | n = treat as a new, separate idea]"

Prevents silently creating a second, disconnected dossier for something already
captured in the backlog.

### 4. Derive the slug

**Mode B (from backlog):** reuse the backlog file's slug verbatim — keeps
`backlog/projects/<slug>.md` and `knowledge/projects/<slug>.md` paired.

**Mode A (raw text):** derive from the idea's title, same convention as the
`idea` skill — lowercase kebab-case, ≤50 chars, strip stop words.

### 5. Target-collision detection

Target path: `$BRAIN/knowledge/projects/<slug>.md`. Three outcomes:

- **File does not exist** → new dossier, continue to step 6.
- **File exists with `kind: idea-dossier`** in its frontmatter → this is a
  previous dossier for the same idea. Show current `Stage:` and `updated:`, ask:
  > "Dossier for `<slug>` already exists (Stage: `<stage>`, updated: `<date>`).
  > Update in place? [y = update | n = abort | new = create a second file with suffix]"
  - `y` → **update mode** (see § Update mode below).
  - `n` → stop.
  - `new` → append `-2` (or next available suffix) to the slug, continue as new.
- **File exists WITHOUT a `kind` field** → this is one of the plain,
  hand-written project reference pages that already live in `knowledge/projects/`
  (existing shipped repos, e.g. `gandalf.md`, `androidlab.md` — a different
  content type, not a dossier). **Do not touch it.** Tell the user:
  > "`<slug>.md` already exists as a project reference page (not a dossier) —
  > likely an unrelated collision. Use a different slug?"
  Offer `<slug>-dossier` or let the user supply one, then continue as new.

### 6. Web research — existing solutions / prior art (default ON)

Unless the user passed `--no-web`, run two targeted passes. Paraphrase and cite
the source URL — never quote verbatim:

**(a) Direct equivalents:**
`"<idea keywords>" existing tool OR project OR app 2025 OR 2026`, plus a
GitHub-flavored pass: `<idea keywords> site:github.com`.

**(b) Adjacent / community discussion:**
`<idea keywords> site:reddit.com OR site:news.ycombinator.com self-hosted OR homelab OR open source`.

If pass (a) returns nothing close, broaden the query once. If prior art is
still sparse or clearly unrelated, do **not** stretch tangential hits into a
fabricated competitive landscape — write plainly: "No close prior art found —
likely novel, or too niche for indexed search coverage."

Suppress web research for a single run with `/develop-idea --no-web <idea>`.

### 7. brain/ profile + goals cross-reference (personalization)

Read `$BRAIN/core/identity/profile.md` and `$BRAIN/core/identity/goals.md`.
Extract: known languages/stack, stated working-style preferences, active goals
and horizons (especially any "Projekty" entries), and explicitly stated
learning gaps. Use this — and only this — to calibrate the dossier's skill-growth
section: what the project would exercise, and how much, relative to what the
user already knows versus is actively trying to learn.

If either file is sparse or placeholder content, say so plainly and keep that
section generic rather than inventing calibration.

### 8. What brain/ already knows (optional, cheap)

```bash
grep -ril "<idea keywords>" "$BRAIN/knowledge/projects/" "$BRAIN/backlog/projects/" 2>/dev/null
```

Collects related existing projects/ideas (e.g. shared tech, overlapping scope
with a sibling GANDALF agent). One grep pass — not a deep scan. If nothing
found: "No related existing projects found in brain/."

### 9. Synthesise the dossier

Compose the full document using the structure below. Do not invent facts —
every claim must trace to the idea text/backlog item, web research (cited),
`profile.md`/`goals.md`, or the brain/ grep in step 8.

---

#### Dossier structure

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
updated: <YYYY-MM-DDTHH:MM:SS>
source: develop-idea
privacy: private
kind: idea-dossier
status: active
origin: inline | backlog
backlog_ref: backlog/projects/<slug>.md   # only present when origin: backlog
effort: <S|M|L|XL|->
tags: [projects, idea-dossier, <topic tags>]
title: "<Idea title>"
---

# <Idea title>

| Field | Value |
|---|---|
| Origin | <pasted text \| promoted from `backlog/projects/<slug>.md`> |
| Captured (backlog) | <original backlog date, if promoted, else "—"> |
| Analysed | <YYYY-MM-DD> |
| Stage | `dossier` |
| Decision | `undecided` |

---

## 1. Idea summary

> Source: <idea text | backlog item>.

<Paraphrase of what the idea is, why, and any context given — no invented detail.>

---

## 2. Merit & feasibility assessment

> Source: reasoning over idea text + core/identity/profile.md + goals.md.

<Technical feasibility, realistic effort vs stated free time/goals, dependency
on other unfinished personal projects, key risks. If it depends on
brain/-adjacent infra not yet ready, say so plainly.>

---

## 3. Existing solutions / prior art

> Source: web research (<query/queries used, URLs cited>).

### Direct equivalents
- **<name>** — <what it does, how close a match> (<URL>)

### Adjacent / inspiration
- **<name>** — <relevance> (<URL>)

### Verdict
<Would this reinvent the wheel, or is there a genuine gap/personalization angle?
If prior art is sparse: "No close prior art found — likely novel, or too niche
for indexed search coverage." Never stretch tangential hits into a fabricated
competitive landscape.>

---

## 4. Proposed execution scenario

> Source: synthesis of idea + feasibility + prior-art findings.

**MVP scope:** <smallest useful version>

**Phased roadmap:**
1. <step>
2. <step>

**First concrete step:** <single actionable next action>

---

## 5. Future expansion ideas

> Source: synthesis — brainstorm beyond MVP.

- <expansion idea>

---

## 6. Skill growth (personalized)

> Source: core/identity/profile.md + core/identity/goals.md.

<What skills this project would exercise and how much — calibrated against
what the user already knows (profile.md) and is actively trying to learn
(goals.md). Flag overlap with a stated goal explicitly. If profile/goals are
sparse, say so and keep this section generic rather than inventing calibration.>

---

## 7. What brain/ already knows (optional)

> Source: grep across knowledge/projects/ and backlog/projects/.

<Related existing projects/ideas found, with file + one-line relevance. If none:
"No related existing projects found in brain/.">

---

## Log

> Append-only. Add a dated entry after each meaningful event.

- <YYYY-MM-DD> — Dossier created.
```

---

### 10. Privacy gate — confirm before writing

Before writing, show the user:

```
── Proposed write ───────────────────────────────────────
File:    <full path to knowledge/projects/<slug>.md>
Mode:    <new file | update in place>
Privacy: private
──────────────────────────────────────────────────────────
⚠️  This dossier is PRIVATE — an explicit override of knowledge/'s public
    default, since it holds personal feasibility and skill-growth
    assessment. In the MVP it may enter the Claude API context window
    (see IMPLEMENTATION.md § "Privacy in the Claude-API MVP").
──────────────────────────────────────────────────────────
If promoting from backlog: also updates
  backlog/projects/<slug>.md (status → done, promoted_to: <path>)
──────────────────────────────────────────────────────────
Change summary:
<sections written, web sources used, brain/ hits found>
──────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write (step 11).
- **n** → discard, stop.
- **edit** → let the user correct content, re-show and ask again.

### 11. Write

Create `$BRAIN/knowledge/projects/` if it does not exist.

**New file:** write the full dossier as synthesised in step 9.

**Update mode:** read the existing file; preserve all sections; merge new
findings in place (§3 prior-art is the section most likely to need refreshing
on a re-run); append a new dated entry to `## Log`; bump `updated:`.

**Mode B (promote from backlog):** also edit `$BRAIN/backlog/projects/<slug>.md`
in place — `status: done`, `updated:` bumped, add `promoted_to:
knowledge/projects/<slug>.md`. Do not delete or move the original file, and do
not touch its body. Both writes are covered by the single gate in step 10.

### 12. Report

```
── Dossier complete ─────────────────────────────────────
✅ Written:  <full path>
   Mode:     <new | updated>
   Stage:    <current stage>
   Origin:   <inline | promoted from backlog/projects/<slug>.md>
   Privacy:  private
─────────────────────────────────────────────────────────
Next: /develop-idea <slug> again to refresh research or move the
      Stage forward once you start building.
```

---

## Update mode & lifecycle

On a re-run against an existing dossier (step 5, `kind: idea-dossier` match),
after merging new findings, ask whether to move the project's own lifecycle
forward:

```
dossier → planned → in-progress → shipped | abandoned
```

Default: unchanged unless the user says otherwise. Also ask about `Decision:`
(`undecided → pursuing | not-pursuing`) — the same two-field pattern as
`analyze-offer`'s Stage/Decision pair.

**`shipped` is left uncompacted.** The skill does not auto-migrate a dossier
into the plain-reference-doc style used by already-shipped projects
(`gandalf.md`-style, no `kind` field) — that conversion, if ever wanted, is a
manual, human-authored step.

### Compact mode — idea abandoned

When the user reports they're not pursuing an idea that already has a full
dossier, compact it on the same update pass instead of leaving all seven
sections in place:

1. Set `Stage: abandoned`, `Decision: not-pursuing`, bump `updated:`.
2. Collapse Sections 1–6 into a single short paragraph under a `## Summary`
   heading — 2–4 sentences: what the idea was, why it was skipped, anything
   worth remembering if it resurfaces.
3. Keep **Section 7** ("what brain/ already knows") only if it found prior
   data — otherwise drop it.
4. Keep `## Log` as-is and append the compaction entry, e.g.
   `<date> — Not pursuing (<short reason>). Dossier compacted.`
5. Confirm the compaction in the privacy gate (step 10) the same as any other
   write — show a diff-style summary, not the full new file, since it's a trim.

---

## Notes

- **One file per idea.** Do not merge multiple ideas into one dossier.
- **`knowledge/projects/` holds two distinct content types.** Plain,
  hand-written reference pages for already-shipped projects (no `kind` field,
  typically `privacy: public`) coexist with this skill's researched dossiers
  (`kind: idea-dossier`, always `privacy: private`). Step 5's collision check
  exists specifically to keep the skill from ever overwriting the former.
  See `knowledge/projects/CLAUDE.md` for the full schema of both types.
- **Living document, not append-only** (except `## Log`, always append-only).
  Edit sections in place as knowledge grows.
- **No invented facts.** Prior-art analysis from web research only; skill-growth
  assessment from `profile.md`/`goals.md` only; related-projects section from
  the brain/ grep only.
- **Web research is default ON.** Pass `--no-web` to skip. The user can also
  ask to skip web mid-session.
- **Backlog promotion accepts any status**, not just `done` — unlike `/idea
  list`'s raw-copy promote (documented for `done` items), this skill's whole
  point is to evaluate an idea *before* it's started. `status: done` on the
  backlog stub after promotion means "capture task superseded by the dossier,"
  not "the project is finished." Both promotion paths coexist: `/idea list`'s
  raw copy stays useful for trivial items not worth researching.
- **Does not touch `_meta/`.** `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory.
- **Privacy:** `privacy: private` is always set, overriding `knowledge/`'s
  folder-level public default — feasibility and skill-growth assessment are
  personal even when the idea itself might otherwise be shareable.
