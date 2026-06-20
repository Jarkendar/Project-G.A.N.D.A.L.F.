# daily

Process a free-form daily note — any domain, not just software (health, finance,
career, projects, ideas, observations, anything) — and route each item to the
right place in `brain/`. Acts as a **dispatcher**: it delegates domain-specific
writes to the skill/convention that already owns that target (`/update-core`,
`/add-contact`, `/ingest-finance`, the `/idea` backlog convention) instead of
duplicating their logic, and keeps a lightweight, append-only daily journal —
no per-day files, just a monthly digest and a yearly index.

## When to use

- End of day (or whenever): `/daily <pasted text>` — process today's note.
- `/daily <path>` — process a note saved to a file (anywhere readable, including
  `brain/current/inbox/`).
- `/daily` with no argument — asks for the note (paste or path).
- Re-running `/daily` for a day already processed — merges new facts in, never
  duplicates the day's journal entry.

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

If `$BRAIN/current/daily/` does not exist:
- Offer to create it (`mkdir` + copy `CLAUDE.md` from
  `.claude/brain-skeleton/current/daily/CLAUDE.md` if present, else a minimal
  one-line note). Proceed only after confirmation. (Normally `/init-brain`
  validation mode scaffolds this automatically — this is a fallback.)

### 2. Gather the note

- `/daily <text>` → the text is the raw note.
- `/daily <path>` → if the argument resolves to an existing file, read it as the
  raw note.
- `/daily` (no argument) → ask: "Wklej dzisiejszą notatkę albo podaj ścieżkę do
  pliku." Wait for the reply.

Determine `$DATE` (ISO `YYYY-MM-DD`): default to today. If the note text itself
references a different day ("wczoraj", an explicit date), confirm the intended
`$DATE` with the user before continuing.

### 3. Check for an existing entry for `$DATE` — idempotency check

Before parsing anything, look up whether this day was already processed:

- `$MONTH_FILE = $BRAIN/current/daily/<YYYY-MM>.md` — does a `## <YYYY-MM-DD>`
  heading for `$DATE` already exist?
- `$YEAR_FILE = $BRAIN/current/daily/<YYYY>.md` — does a row for `$DATE` already
  exist in the table?

Set `$DAY_MODE`:
- Neither exists → **new entry**.
- Either exists → **update entry**. Show the user the existing section/row
  content before proceeding — new material will be merged into it, never
  duplicated alongside it.

This mode is carried through to the routing plan (step 6) and the write step (step 7).

### 4. Parse into discrete items

Break the note into atomic facts/events — one item per distinct piece of
information (a measurement, an expense, a contact met, an idea, a project
update, an observation, etc.). Keep the user's wording; do not invent or infer
facts beyond what's written.

Also draft, but don't write yet:
- A **terse digest** of the whole day — 2–4 bullets, for the monthly file.
- A **one-line summary** of the whole day, for the yearly index row.

These are compressions of the day, independent of the itemised routing below.

### 5. Classify and route each item

| Item type | Target | Mechanism (mirrors) |
|---|---|---|
| Health/body metric or condition | `core/health/*` | `/update-core` format |
| Finance note or portfolio change | `core/finance/finance.md` or a myFund export | `/update-core` format / point to `/ingest-finance` if it's an export |
| New or updated contact | `core/contacts/` | `/add-contact` format |
| Identity/goal change | `core/identity/*` | `/update-core` format |
| Idea / to-do / "remember this" | `backlog/<domain>/` | `/idea` Mode A format |
| Project status / working-state update | `current/context/<project>.md` | direct edit-in-place |
| General note, observation, learning (no other home) | `knowledge/notes/` | direct new file |
| Day digest (always, regardless of other items) | `current/daily/` aggregates | direct append/merge (step 7) |
| Unclear / not enough info | — | flag ❓, resolve in step 5b or skip |

If an item could fit more than one row, prefer the more specific target
(e.g. a weight reading is health, not a general note).

### 5b. Resolve gaps before building the plan

Some delegated formats need a field the note doesn't supply (e.g. `/add-contact`
needs a role/group; `/idea` needs a domain/effort). Batch all such gaps into a
**single** follow-up question covering every item that needs one — do not ask
one at a time. If the user skips a question, fall back to a sane default
(domain: `notes`, effort: `—`, contact group: ask user to pick from existing
headings or default to a generic one) and flag it in the plan.

### 6. Build the routing plan — one proposal, shown once

```
── Daily routing plan — <DATE> (<NEW | UPDATE>) ───────────────────────
 #  Item                                   Target                          Mode      Privacy
 1  <short paraphrase>                     core/health/body.md             update    private
 2  <short paraphrase>                     backlog/check/<slug>.md         new       private
 3  <short paraphrase>                     current/context/job-search.md   update    private
 4  <short paraphrase>                     knowledge/notes/<slug>.md       new       private
 ❓ <item with unresolved gap>               —                               —         —
────────────────────────────────────────────────────────────────────────
Daily journal (always):
   current/daily/<YYYY-MM>.md   <new section | merge into existing>
   current/daily/<YYYY>.md      <new row | update existing row>
────────────────────────────────────────────────────────────────────────
⚠️  Items targeting core/ or current/ are PRIVATE — stay on this machine.
    MVP exception: may enter the Claude API context window (see
    IMPLEMENTATION.md § "Privacy in the Claude-API MVP").
────────────────────────────────────────────────────────────────────────
Proceed? [y / n / edit]
```

- **y** → execute step 7 for every row exactly as shown.
- **n** → discard everything, stop. Nothing is written.
- **edit** → let the user drop, reclassify, or correct individual rows
  (including dropping a `❓` row entirely), then re-show the plan and ask again.

This is the **only** confirmation. Do not re-open a privacy gate per item or
per delegated format in step 7 — the plan above already covers all of them.

### 7. Execute writes (after `y`)

For each accepted row, write in the **exact frontmatter/file shape of the
mirrored skill**, so the result is indistinguishable from that skill having
written it directly:

- **Health / identity / goals / finance (core/)** — mirror `/update-core`:
  edit the target living document in place, preserve other sections, bump
  `date:` to now, keep `source: manual` (the fact still originates from the
  user, just captured via `/daily`). Append-only measurement-log rows
  (e.g. `core/health/body.md`) are appended, never edited.
- **Contacts** — mirror `/add-contact`: index row in `core/contacts/contacts.md`
  (+ detail file only if warranted per its own rules), `source: manual`.
- **Backlog item** — mirror `/idea` Mode A's file template exactly
  (`backlog/<domain>/<slug>.md`, `source: idea`, `status: idea`, frontmatter
  fields `date`, `updated`, `domain`, `effort`, `tags`, `title`). Use the same
  slug rule (lowercase kebab-case, ≤40 chars, diacritics transliterated per
  `add-contact.md`'s map).
- **Project context update** — find the matching `current/context/<slug>.md`
  by name/keyword. Read it, insert the new fact under the most relevant
  existing section (or add a small new section) matching its existing style —
  there is no fixed template here (see `job-search.md` for the freeform,
  status-glyph style in active use). Bump `date:`. If no matching project file
  exists, ask once whether to create
  `current/context/<slug>.md` (`status: draft`) or route the item to
  `knowledge/notes/` instead.
- **General note** — new file `knowledge/notes/<YYYY-MM-DDTHH-MM-SS>_daily_<slug>.md`:
  ```yaml
  date: <now, ISO 8601>
  source: daily
  privacy: private   # default private unless clearly generic/public; ask if unsure
  status: active
  tags: [daily, <1-3 topical tags>]
  title: "<short title>"
  ```
  followed by a short body (the item, in the user's words, plus minimal context).

#### Daily journal aggregates (always, both files, every run)

**Monthly file** `$BRAIN/current/daily/<YYYY-MM>.md`:
```yaml
date: <first-write ISO 8601>     # set once, on creation
updated: <now, ISO 8601>          # bumped every write
source: daily
privacy: private
status: active
tags: [daily, journal, <YYYY-MM>]
title: "Daily journal — <YYYY-MM>"
```
```markdown
# Daily journal — <YYYY-MM>

> Aggregated, terse daily digest. One section per day, 2–4 bullets. Append-only:
> a new day gets a new `## YYYY-MM-DD` section appended at the end; an existing
> day's section is merged (new, non-duplicate bullets added to it) — never
> duplicated or rewritten wholesale. No per-day files are kept.

## <YYYY-MM-DD>
- <bullet>
- <bullet>
```
If file doesn't exist yet, create it with the frontmatter above and the first
section. If `$DAY_MODE` is **update**, locate the existing `## <DATE>` section
and append only bullets not already present (compare case-insensitively,
ignoring punctuation) — do not touch other days' sections.

**Yearly file** `$BRAIN/current/daily/<YYYY>.md`:
```yaml
date: <first-write ISO 8601>
updated: <now, ISO 8601>
source: daily
privacy: private
status: active
tags: [daily, journal, <YYYY>]
title: "Daily journal index — <YYYY>"
```
```markdown
# Daily journal index — <YYYY>

> One row per day, one-line summary. Append-only — up to 365 rows/year. An
> existing day's row is edited in place (never duplicated) when `/daily` runs
> again the same day; combine old + new summary with `; ` if both add value.

| Date | Summary |
|---|---|
| <YYYY-MM-DD> | <one-line summary> |
```
If `$DAY_MODE` is **update**, edit that day's existing row in place instead of
appending a new one.

### 8. Report

```
── /daily complete — <DATE> (<NEW | UPDATE>) ───────────────────────────
✅ core/health/body.md           updated (measurement log +1 row)
✅ backlog/check/<slug>.md       written
✅ current/context/job-search.md updated
✅ knowledge/notes/<slug>.md     written
✅ current/daily/<YYYY-MM>.md    <new section | merged>
✅ current/daily/<YYYY>.md       <new row | row updated>
⏭️  <item>                        skipped (dropped in edit)
❓ <item>                         left unresolved — not written
────────────────────────────────────────────────────────────────────────
```

---

## Notes

- **Delegation means format-mirroring, not re-invocation.** `/daily` does not
  programmatically call `/update-core` etc. — it follows their documented file
  shape directly, inside this skill's own single gate (step 6, executed in
  step 7). This avoids a second nested confirmation per delegated write.
- **One gate, period.** All writes — core/, backlog/, context/, notes/, and the
  daily aggregates — are covered by the single plan confirmation in step 6.
- **No invented facts.** Every written fact must trace back to the user's note.
  Ambiguous items are flagged and either resolved via the step 5b batch question
  or left unwritten — never guessed.
- **Idempotent daily aggregates.** Re-running `/daily` for a day already logged
  merges into the existing section/row (step 3 + step 7) — it never creates a
  second section or a duplicate row for the same date.
- **No per-day files.** `current/daily/` holds only the rolling monthly digest
  and yearly index — by design, to keep the journal from sprawling into 365
  small files a year.
- **Privacy.** `core/` and `current/` targets are always PRIVATE (folder-level
  rule, `_meta/schema.md`). `knowledge/notes/` defaults to private when unclear
  — only mark `public` when the content is clearly generic/non-personal.
- **Does not touch `_meta/`** — `queue.jsonl` and `manifest.json` are Bilbo /
  Treebeard territory.
- **New `source:` value.** Items written directly by this skill (daily
  aggregates, context updates, general notes) use `source: daily` — a new
  value alongside the illustrative list in `brain/_meta/schema.md` (that list
  is documentation, not an enforced enum, so no schema change is required for
  this skill to work; updating the doc for completeness is optional, owner's
  call, in the `brain/` repo).
- **Templates for delegated targets stay in their own skills.** This skill
  does not re-embed `/update-core`, `/add-contact`, `/idea`, or
  `/ingest-finance`'s templates beyond what's needed to route correctly — if
  those change, update them there, not here.
