---
name: idea
description: >-
  Capture a personal idea, note, or to-do item into brain/backlog/, or list and
  manage the existing backlog (one file per idea, lightweight frontmatter).
  Use this skill when saving any idea, thing-to-check, thing-to-create, or
  reminder for later, when reviewing the backlog and deciding what to do next,
  when changing an item's status (active/done/dropped), or whenever the user
  says "save this as an idea" / "add to backlog" / "dorzuć do backlogu" /
  "zapisz to jako pomysł" mid-conversation without an explicit /idea invocation.
---

# idea

Capture a personal idea, note, or to-do item into `brain/backlog/`, or list and
manage the existing backlog. One file per idea — descriptive filename, lightweight
frontmatter, 2–6 lines of context.

Works in three modes:
- **capture** (default) — save a new item.
- **list / plan** — show the backlog, change status, prioritise.
- **inline** — triggered mid-conversation when the user says "save this as an idea",
  "add to backlog", or similar, without an explicit `/idea` invocation.

## When to use

- Saving any idea, note, thing-to-check, thing-to-create, or reminder for later.
- Reviewing what's in the backlog and deciding what to do next.
- Changing the status of an item (active, done, dropped).
- Mid-conversation: whenever the user wants to capture something without interrupting
  the current flow.

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

If `$BRAIN/backlog/` does not exist:
- Offer to create it (mkdir + CLAUDE.md skeleton). Proceed only after confirmation.

### 2. Determine mode

Check the argument passed to the skill:

- **`/idea list`** or **`/idea plan`** → go to **Mode B: list**.
- **`/idea <text>`** → go to **Mode A: capture** with the provided text as the raw idea.
- **`/idea`** (no argument) → ask: "What's the idea?" Wait for the user's reply, then
  go to **Mode A: capture**.
- **Inline trigger** (no explicit `/idea`, but user says "save as idea", "add to backlog",
  "remember this", "dorzuć do backlogu", "zapisz to jako pomysł", etc.) → go to
  **Mode A: capture** using the referenced content from the conversation.

---

### Mode A — Capture

#### A1. Understand the raw idea

If the raw idea text is terse (< 10 words), ask one brief follow-up:
> "Any context — why this, rough effort, or which area of life?"

If the user declines or it's already clear, proceed with what you have.

#### A2. Propose classification

Derive and show the user the proposed metadata before asking for confirmation:

```
── Proposed item ────────────────────────────────────────
Title:   <concise human-readable title, ≤60 chars>
Domain:  <projects | activities | check | create | remember | notes>
Effort:  <S | M | L | XL | — >    (rough: S=<1h, M=<1day, L=<1week, XL=big)
Tags:    [<3-5 lowercase tags>]
File:    $BRAIN/backlog/<domain>/<slug>.md
─────────────────────────────────────────────────────────
Correct anything? [y = adjust | n = write]
```

**Domain guide:**
- `projects` — idea for a project (software, homelab, creative)
- `activities` — free time, new activity, trip, experience
- `check` — something to research, read, verify, or look into
- `create` — something to make (recipe, 3D print, tool, document)
- `remember` — reminder without a hard date; something not to forget
- `notes` — loose note / catch-all when nothing else fits

**Slug:** lowercase kebab-case from title, max 40 chars, no stop words.

On `y`: let the user adjust title, domain, effort, or tags inline, then re-show.
On `n`: proceed to A3.

#### A3. Compose the file body

Write 2–6 lines describing:
- What the idea is.
- Why / context / motivation (if known).
- Optional: first step, links to related `brain/` files.

Do not invent facts. Use only what the user provided.

#### A4. Privacy gate — confirm before writing

```
── Proposed write ───────────────────────────────────────
File:    $BRAIN/backlog/<domain>/<slug>.md
Mode:    new file
Privacy: private
─────────────────────────────────────────────────────────
⚠️  backlog/ is PRIVATE — stays on this machine. In the MVP it may
    enter the Claude API context window (see IMPLEMENTATION.md §
    "Privacy in the Claude-API MVP"). Phase 2 closes this exception.
─────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write (A5).
- **n** → discard, stop.
- **edit** → let the user correct the body, re-show and ask again.

#### A5. Write

Create `$BRAIN/backlog/<domain>/` if it does not exist.

Write `$BRAIN/backlog/<domain>/<slug>.md`:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
updated: <YYYY-MM-DDTHH:MM:SS>
source: idea
privacy: private
status: idea
domain: <domain>
effort: <S|M|L|XL|->
tags: [<tags>]
title: "<title>"
---

# <title>

<2–6 lines of body>
```

#### A6. Report

```
── Idea captured ─────────────────────────────────────────
✅ Written: $BRAIN/backlog/<domain>/<slug>.md
   Title:   <title>
   Domain:  <domain>
   Status:  idea
──────────────────────────────────────────────────────────
Use `/idea list` to review and prioritise the backlog.
```

---

### Mode B — List / Plan

#### B1. Read the backlog

Find all `.md` files in `$BRAIN/backlog/**/*.md` (excluding `CLAUDE.md`).
Read each file's frontmatter. Collect: title, domain, status, effort, date, updated.

If the backlog is empty, say so and stop.

#### B2. Show the table

Group by domain, sort within each group by status then date (oldest first):

```
── Backlog ──────────────────────────────────────────────

projects (N items)
  [status]  <title>                [effort]  <age>   <slug>
  ──────────────────────────────────────────────────────

activities (N items)
  ...

check / create / remember / notes ...

Legend: 💡 idea  ▶ active  ✅ done  ✗ dropped
─────────────────────────────────────────────────────────
```

#### B3. Offer actions

After showing the table, ask:

> "What do you want to do?
> - Change status of an item (type the slug + new status: active / done / dropped)
> - Show full details of an item (type the slug)
> - Promote a done item to `knowledge/projects/` (type: promote <slug>)
> - Nothing — just reviewing (Enter / 'done')"

Repeat until the user is done or says "done" / "exit" / "koniec".

#### B4. Execute actions

**Status change:** edit the matching file's frontmatter: update `status:` and bump
`updated:` to current datetime. Show the change; confirm before writing.

**Show details:** print the full file content.

**Promote:** copy the file to `$BRAIN/knowledge/projects/<slug>.md` with updated
frontmatter (`status: active`, `privacy: private`, bump `date:`). Show the proposed
copy + gate; confirm before writing. Do NOT delete the original — append-only rule;
update original's status to `done` and add a note: `promoted_to: knowledge/projects/<slug>.md`.

---

## Notes

- **Inline trigger:** the inline capture mode is always active — no `/idea` invocation
  needed. When the user says "zapisz to jako pomysł", "dorzuć do backlogu", "save as idea",
  or similar, treat it as a Mode A capture using the referenced content.
- **Does not touch `_meta/`** — queue.jsonl and manifest.json are Bilbo / Treebeard
  territory.
- **Append-only:** done and dropped items stay in place. Delete nothing.
- **No hard deadlines or reminders** — that is F.A.R.A.M.I.R.'s domain. backlog/ is
  for ideas without a calendar anchor.
- **Domain is extensible** — if a user's idea doesn't fit any existing subfolder, propose
  a new one and create it. Update `$BRAIN/backlog/CLAUDE.md` to document the new domain.
- **No invented facts** — body content comes from the user only.
