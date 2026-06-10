# update-core

Add or update personal facts in `brain/core/`. Edits the appropriate living document
in place — profile, goals, contacts, health, body, or finance.

## When to use

- Recording a new personal fact (name, location, role, language, preference)
- Updating a goal, horizon, or priority
- Adding or changing a contact / relationship note
- Recording a health datum — condition, allergy, medication, vaccination (only on explicit user request)
- Recording a body parameter or a new measurement (height, weight, vitals) (only on explicit user request)

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
Call it `$BRAIN`.

### 2. Verify core/ exists

Check that `$BRAIN/core/` exists.

If missing: tell the user "Run `/init-brain` first to scaffold the brain/ repo." Stop.

### 3. Identify the target document

Route the user's intent to one of six living documents:

| Category | Target file |
|---|---|
| Identity — name, location, role, languages, background, preferences | `$BRAIN/core/identity/profile.md` |
| Goals — horizons, active goals, someday/maybe | `$BRAIN/core/identity/goals.md` |
| Contacts — people, relationships, context | `$BRAIN/core/identity/contacts.md` |
| Health — conditions, allergies, meds, vaccinations, habits | `$BRAIN/core/health/health.md` |
| Body parameters — height, weight, body composition, vitals, measurement log | `$BRAIN/core/health/body.md` |
| Finance — accounts, budget, financial notes | `$BRAIN/core/finance/finance.md` |

If the intent covers multiple documents, handle them one by one.

If the target file does not exist: tell the user to run `/init-brain` (validation
mode) — it will scaffold the missing file from the skeleton template. Stop.

### 4. Read and gather

Read the current content of the target document.
Show the user the relevant section and ask what to add or change.

Do not invent facts. Every fact must come from the user.

### 5. Edit in place

Insert the new fact into the appropriate section, or update existing content.

Rules:
- Edit the file in place — this is a living document.
- Preserve all other sections and content verbatim.
- Match the markdown style of the existing content (bullet lists, headers, etc.).
- Do not delete existing content unless the user explicitly asks.
- **`body.md` measurement log exception:** `## Current snapshot` fields are
  edited in place (latest value replaces previous). Rows in `## Measurement log`
  are **append-only** — never edit or delete a past row. This aligns with
  principle #5 (append-only with supersession).

### 6. Bump frontmatter

After editing, update the `date:` field in frontmatter to the current ISO 8601
datetime. This is the *last-updated* timestamp, not the creation date.

Required frontmatter fields after any edit:
```yaml
date: <current YYYY-MM-DDTHH:MM:SS>
source: manual
privacy: private
status: active
tags: [<at least one relevant tag>]
```

### 7. Optional supersession for major revisions

If the user wants to preserve a complete history of a major change (e.g. change of
job, address, or a significant life event), offer to archive the pre-edit version:

1. Copy the current file to `$BRAIN/archive/YYYY-MM-DDTHH-MM-SS_superseded_<slug>.md`
   before editing.
2. Add `supersedes: archive/YYYY-MM-DDTHH-MM-SS_superseded_<slug>.md` to the new
   version's frontmatter.
3. Note: T.R.E.E.B.E.A.R.D. will later set `superseded_by:` in the archived copy.

Default: skip archiving, edit in place. Offer only when the change is substantial.

### 8. Privacy gate — confirm before writing

Before writing, tell the user:
- Which file will be changed.
- What the change is (a short diff summary).
- Reminder: `core/` content is PRIVATE and stays on this machine. In the MVP,
  it may enter the Claude API context window (see IMPLEMENTATION.md §
  "Privacy in the Claude-API MVP"). Phase 2 closes this exception.

Ask: "Write this change? (y / n / edit)"

On `y`: write the file.
On `n`: discard, stop.
On `edit`: let the user correct the content, then re-confirm.

### 9. Report

After writing, print:
- File path updated.
- Section(s) modified.
- New `date:` value in frontmatter.

---

## Notes

- **Manual only.** No automation writes to `core/`. This skill is the only
  authorised automated path — and even here, every write requires explicit user
  confirmation (step 8).
- **Living documents, not append-only.** `core/` uses the living-document model
  (slug.md files edited in place), not the timestamped-file model used by `inbox/`.
  The `date:` field is last-updated, not creation time.
- **No queue / manifest updates.** `_meta/queue.jsonl` and `_meta/manifest.json`
  are Bilbo and Treebeard territory — this skill does not touch them.
- **Privacy.** `core/` is PRIVATE. Content stays local. See `core/CLAUDE.md` for
  the full privacy rules and the MVP exception in IMPLEMENTATION.md.
- **Supersession is opt-in.** The default path is always edit-in-place. Archiving
  the previous version is offered only for substantial, history-worthy changes.
- **File templates.** The canonical templates for all `core/` documents live in
  `.claude/brain-skeleton/` in the G.A.N.D.A.L.F. repo. This skill no longer
  embeds them. To initialise a missing document, run `/init-brain` (validation mode).
