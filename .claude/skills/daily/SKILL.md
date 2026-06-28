---
name: daily
description: >-
  Process a free-form daily note covering any domain (health, finance, career,
  projects, ideas, observations) and route each item into brain/, delegating to
  the skill that already owns that target (update-core, add-contact, idea,
  ingest-finance) while maintaining a lightweight, append-only daily journal.
  A mention of a sport activity (run, ride, swim, etc.) triggers a live lookup
  via the Strava MCP, logged to a parallel monthly/yearly fitness digest.
  Mentions of visited places (restaurants, bars, attractions, cities) route to
  knowledge/places/; attended events (concerts, races, airshows, festivals,
  trips, kayak trips) route to knowledge/events/. Use this skill when capturing
  an end-of-day note, processing a note saved to a file, or re-running for a
  day already processed to merge in new facts without duplicating the day's
  journal entry.
---

# daily

Process a free-form daily note — any domain, not just software (health, finance,
career, projects, ideas, observations, anything) — and route each item to the
right place in `brain/`. Acts as a **dispatcher**: it delegates domain-specific
writes to the skill/convention that already owns that target (`/update-core`,
`/add-contact`, `/ingest-finance`, the `/idea` backlog convention) instead of
duplicating their logic, and keeps a lightweight, append-only daily journal —
no per-day files, just a monthly digest and a yearly index. When the note
mentions a sport activity, it additionally fetches the structured truth from
Strava (via the `strava` MCP server) and logs it to a second, parallel
monthly-digest-plus-yearly-index pair scoped to fitness data.

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

If `$BRAIN/current/fitness/` does not exist:
- Same fallback (`mkdir` + copy `CLAUDE.md` from
  `.claude/brain-skeleton/current/fitness/CLAUDE.md`). Only needed the first
  time a sport-activity mention is detected (step 5b) — don't create it
  pre-emptively if today's note has no such mention.

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
| Sport activity mention (run, ride, swim, etc.) | `current/fitness/` aggregates | Strava MCP lookup (step 5b) |
| Finance note or portfolio change | `core/finance/finance.md` or a myFund export | `/update-core` format / point to `/ingest-finance` if it's an export |
| New or updated contact | `core/contacts/` | `/add-contact` format |
| Identity/goal change | `core/identity/*` | `/update-core` format |
| Idea / to-do / "remember this" | `backlog/<domain>/` | `/idea` Mode A format |
| Project status / working-state update | `current/context/<project>.md` | direct edit-in-place |
| Visited place (restaurant, bar, café, attraction, venue, city) | `knowledge/places/<slug>.md` | new file or add visit row to existing (step 5d) |
| Attended event (concert, race, festival, airshow, trip, kayak, etc.) | `knowledge/events/<YYYY-MM-DD>_<slug>.md` | new file; venue also gets a place entry (step 5d) |
| General note, observation, learning (no other home) | `knowledge/notes/` | direct new file |
| Day digest (always, regardless of other items) | `current/daily/` aggregates | direct append/merge (step 7) |
| Unclear / not enough info | — | flag ❓, resolve in step 5c or skip |

**Place vs event distinction:**
- **Place** — the note describes visiting a location (restaurant, landmark, shop, city). No
  programmatic itinerary; could be revisited multiple times. One living file accumulates visits.
- **Event** — the note describes attending something with its own programme: concert, race,
  airshow, multi-day trip, festival, guided kayak trip, etc. One file per edition/occurrence.
  If the event has a physical venue, that venue also gets a `knowledge/places/` entry.
- Gray area rule: if uncertain, ask the user in the step 5c batch question.

If an item could fit more than one row, prefer the more specific target
(e.g. a weight reading is health, not a general note).

A sport-activity mention only carries the **objective stats** (distance, time,
pace, HR) to `current/fitness/` — sourced from Strava, not the user's typed
numbers (chip time vs GPS time can legitimately differ). Any **subjective**
commentary in the same note (how it felt, technique, goals) still classifies
as Health/body and routes to `core/health/health.md` as before, unaffected by
this change.

### 5b. Strava lookup for sport-activity items

For each item classified as a sport-activity mention:

1. Check availability: call `mcp__strava__check-strava-connection`.
   - Not connected / errors → flag "⚠️ Strava not connected — logged as
     narrative only", skip the lookup. The item still routes through the
     normal classification table (e.g. subjective notes still reach
     `health.md`) — nothing is lost, the structured fitness entry is just
     not created this run.
2. Call `mcp__strava__get-all-activities` with `startDate` = `endDate` =
   `$DATE`. If zero results, retry once with a `$DATE - 1` … `$DATE + 1` window
   (handles local-time/UTC boundary cases) before giving up.
3. Match candidates against the note's own description — activity type
   (run/ride/swim/...) and, if stated, approximate distance or time of day.
   - Exactly one match → continue to 4.
   - Multiple plausible matches → list them (type, distance, start time);
     queue a disambiguation question, batched into the single question in
     step 5c (do not ask separately).
   - Zero matches → flag "⚠️ No matching Strava activity found for `$DATE`",
     skip the lookup (same non-blocking fallback as step 1).
4. Call `mcp__strava__get-activity-details` for the matched activity ID.
   (Optional: `mcp__strava__get-activity-laps` only if the note explicitly
   calls out splits/intervals.)
5. From the response, build a **structured** summary — type, distance,
   moving time, pace/speed, elevation gain, avg/max heart rate, calories,
   device — for use in the routing plan preview (step 6) and the write
   (step 7 § Sport activity aggregates). This replaces the user's typed
   numbers for these fields; it does not touch any subjective commentary.
6. **Resolve heart-rate zone boundaries** (only if the matched activity has
   heart-rate data). Check sources in order, stop at the first hit:
   - `$BRAIN/core/health/body.md`, section `## Heart rate zones` — if present,
     use these boundaries. Source: `body.md`.
   - Otherwise call `mcp__strava__get-athlete-zones` — if the athlete has
     zones configured there, use them. Source: `Strava`. Queue a one-time
     proposal to persist these into `core/health/body.md` (see step 7) so
     future runs don't need this lookup — at most one such proposal per run,
     regardless of how many activities matched.
   - Otherwise compute a generic estimate: max HR via Tanaka
     (`208 − 0.7 × age`; age from `body.md`'s date of birth — if that's also
     missing, add a single question to the step 5c batch rather than
     guessing), then standard 5-zone bands at 50/60/70/80/90% of max HR.
     Source: `estimated (Tanaka)`. Queue the same one-time save proposal,
     clearly labelled as an estimate.
7. Fetch the heart-rate stream: `mcp__strava__get-activity-streams` with
   `types: ["time", "heartrate"]`, `series_type: "time"`. For each consecutive
   pair of points, add the time delta to whichever zone contains the heart
   rate at the start of that interval; sum into per-zone minutes for the
   activity. If the activity has no heart-rate stream, skip and flag
   "no HR data" rather than guessing.

8. **Stage the fitness DB upsert** (executed in step 7, not here). Record the
   following fields from the `get-activity-details` response for the upsert:
   `strava_id`, `date` (YYYY-MM-DD from activity start), `sport_type`, `name`,
   `distance_m` (metres), `moving_time_s` (seconds), `elapsed_time_s` (total
   elapsed time including pauses), `elevation_m` (total elevation gain),
   `average_hr` (integer, NULL if absent), `max_hr` (integer, NULL if absent),
   `average_cadence` (steps/min or rpm, NULL if absent), `average_speed` (m/s,
   NULL if absent), `average_watts` (NULL if absent — cycling power meter only),
   `calories` (Strava calorie estimate, NULL if absent), `suffer_score` (integer,
   NULL if absent), `kilojoules` (NULL if absent), `workout_type` (Strava enum
   integer, NULL if absent — e.g. 1=race, 2=long run, 3=workout for Run).
   Nullable fields use SQL NULL when absent from the API response — never 0.

### 5c. Resolve gaps before building the plan

Some delegated formats need a field the note doesn't supply (e.g. `/add-contact`
needs a role/group; `/idea` needs a domain/effort; a sport-activity item may
need the Strava disambiguation from 5b.3 or a missing date-of-birth for a zone
estimate from 5b.6). Batch all such gaps into a **single** follow-up question
covering every item that needs one — do not ask one at a time. If the user
skips a question, fall back to a sane default (domain: `notes`, effort: `—`,
contact group: ask user to pick from existing headings or default to a generic
one; an unresolved Strava match falls back to narrative-only, per 5b; a
missing DOB skips zone-time computation for this run) and flag it in the plan.

For **place** items, gaps that warrant a batch question:
- `type` if unclear from context (restaurant / bar / café / attraction / venue / city / other)
- Rating if the note expresses an opinion but doesn't make it obvious (★★★★★ świetne →
  ★☆☆☆☆ odradzam); skip if the note is neutral or purely factual.

For **event** items, extract from the note what's available; batch-ask only what's
missing and material:
- `event_type` if unclear
- `with` (who was there) — only if not mentioned and relevant
- `travel` / `accommodation` — only if the event was out-of-town and the note is silent

### 5d. Place / event file resolution

Before building the routing plan, determine whether a place file already exists:

```
$BRAIN/knowledge/places/<slug>.md
```

where slug = `<name>-<city>` in kebab-case (diacritics stripped: ą→a, ę→e, ó→o,
ś→s, ź/ż→z, ć→c, ń→n, ł→l). Search case-insensitively; also try just `<name>.md`
if the city is already in the name.

- **File exists** → `$PLACE_MODE = update` (add a visit row; do not rewrite the file).
- **File does not exist** → `$PLACE_MODE = new` (create the full file from the schema).

For event items, always `$EVENT_MODE = new` (events are one-off). Exception: if
`/daily` is re-run for the same `$DATE` and a file `knowledge/events/<YYYY-MM-DD>_<slug>.md`
already exists, treat it as `update` and merge new information in.

### 6. Build the routing plan — one proposal, shown once

```
── Daily routing plan — <DATE> (<NEW | UPDATE>) ───────────────────────
 #  Item                                   Target                          Mode      Privacy
 1  <short paraphrase>                     core/health/body.md             update    private
 2  <activity type>, Strava: <dist> <time> avgHR <bpm>   current/fitness/<YYYY-MM>.md   new   private
 3  <short paraphrase>                     backlog/check/<slug>.md         new       private
 4  <short paraphrase>                     current/context/job-search.md   update    private
 5  <short paraphrase>                     knowledge/notes/<slug>.md       new       private
 6  HR zones (Strava | estimated) → save  core/health/body.md             new       private
 ❓ <item with unresolved gap>               —                               —         —
────────────────────────────────────────────────────────────────────────
Daily journal (always):
   current/daily/<YYYY-MM>.md   <new section | merge into existing>
   current/daily/<YYYY>.md      <new row | update existing row>
Fitness journal (when a sport activity was matched in step 5b):
   current/fitness/<YYYY-MM>.md   <new entry | merge into existing>
   current/fitness/<YYYY>.md      <new month row | update existing row>
   brain/db/fitness.db            upsert (INSERT OR REPLACE, keyed on strava_id)
────────────────────────────────────────────────────────────────────────
⚠️  Items targeting core/ or current/ are PRIVATE — stay on this machine.
    MVP exception: may enter the Claude API context window (see
    IMPLEMENTATION.md § "Privacy in the Claude-API MVP").
────────────────────────────────────────────────────────────────────────
Proceed? [y / n / edit]
```

Row 6 (HR zones save) only appears the first time `core/health/body.md` has
no `## Heart rate zones` section yet — omit it entirely on every later run.

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
- **Place** — follow the schema in `knowledge/places/CLAUDE.md`:
  - `$PLACE_MODE = new`: create `knowledge/places/<slug>.md` with full frontmatter
    (`type`, `city`, `address` if known, `cuisine` if restaurant, `visited` list,
    required brain/ fields) and body sections (Ogólna ocena + Wizyty table).
    Rating scale: ★★★★★ świetne / ★★★★☆ dobre / ★★★☆☆ przeciętne /
    ★★☆☆☆ słabe / ★☆☆☆☆ odradzam. Omit rating row if the note is neutral.
  - `$PLACE_MODE = update`: read the existing file; append one row to the
    `## Wizyty` table (date, occasion, rating if expressed, notes). Bump `updated:`.
    Do not rewrite other sections.
  - Always `privacy: private` (contains personal data — who was there, opinions).

- **Event** — follow the schema in `knowledge/events/CLAUDE.md`:
  - Create `knowledge/events/<YYYY-MM-DD>_<slug>.md` where the date is `date_start`
    and slug is the event name in kebab-case (≤40 chars, diacritics stripped).
  - Include all frontmatter fields extractable from the note (`event_type`, `city`,
    `with`, `travel`, `accommodation`, `venue` pointer). Omit fields the note
    doesn't mention — never guess.
  - Body: write only the sections that have content from the note. Minimum: one
    sentence in `## Wydarzenie`. Sections `## Jak dotarłem` and `## Nocleg` only
    if the note mentions travel/overnight. `## Wrażenia` if the note includes
    subjective impressions. `## Highlights` if there are clear standout moments.
  - If the event has a physical venue, also create/update the corresponding
    `knowledge/places/` entry (apply place write rules above for the venue).
  - Always `privacy: private`.

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

#### Sport activity aggregates (only when an item matched in step 5b)

Unlike the daily journal above, these two files are written **only** when a
Strava match was found — not every run. Entries are keyed by **Strava activity
ID**, not by date, since a single day can hold more than one activity.

**Monthly file** `$BRAIN/current/fitness/<YYYY-MM>.md`:
```yaml
date: <first-write ISO 8601>     # set once, on creation
updated: <now, ISO 8601>          # bumped every write
source: daily
privacy: private
status: active
tags: [fitness, strava, journal, <YYYY-MM>]
title: "Fitness journal — <YYYY-MM>"
```
```markdown
# Fitness journal — <YYYY-MM>

> Structured digest of Strava activities, fetched via the Strava MCP when
> /daily detects a sport-activity mention (step 5b). Append-only: a new
> activity gets a new section; re-running /daily for an already-logged
> activity (same Strava ID) updates that section in place — never duplicated.
> No per-activity files are kept.

## Month totals
- Activities: <count>
- Distance: <sum> km
- Moving time: <sum, H:MM:SS>
- Avg HR (duration-weighted): <value> bpm
- Zone time: Z1 <min> · Z2 <min> · Z3 <min> · Z4 <min> · Z5 <min> (minutes, summed)

## <YYYY-MM-DD> — <activity type/name> (Strava ID: <id>)
- Distance: <km>, Moving time: <H:MM:SS>, Pace/speed: <value>
- Avg HR: <bpm> (max <bpm>), Elevation gain: <m>
- Zone time: Z1 <min> · Z2 <min> · Z3 <min> · Z4 <min> · Z5 <min> (minutes;
  omit this line entirely if step 5b.7 found no HR stream)
- Zone source: <body.md | Strava | estimated (Tanaka)>
- Device: <e.g. from the Strava activity description>
```
If the file doesn't exist yet, create it with the frontmatter above and the
first section, plus an initial "Month totals" block. Recompute "Month totals"
from all sections in the file on every write (cheap — at most ~30 entries).
If updating an existing activity (same Strava ID), replace its section in
place and recompute totals; never append a duplicate section for the same ID.

**Yearly file** `$BRAIN/current/fitness/<YYYY>.md`:
```yaml
date: <first-write ISO 8601>
updated: <now, ISO 8601>
source: daily
privacy: private
status: active
tags: [fitness, strava, journal, <YYYY>]
title: "Fitness journal index — <YYYY>"
```
```markdown
# Fitness journal index — <YYYY>

> One row per month, aggregated totals — mirrors the "Month totals" block of
> the corresponding monthly file. Updated in place as the month accumulates
> activities; never duplicated.

| Month | Activities | Distance | Moving time | Avg HR | Zones Z1-Z5 (min) |
|---|---|---|---|---|---|
| <YYYY-MM> | <count> | <sum> km | <H:MM:SS> | <bpm> | <min/min/min/min/min> |
```
Edit the current month's row in place (recomputed from the monthly file);
never append a second row for a month already present. Leave the zones column
`—` for months where no activity had HR-stream data.

#### Fitness DB upsert (only when step 5b matched)

For each matched Strava activity, write to `$BRAIN/db/fitness.db` using the
fields staged in step 5b.8. This is the only direct SQLite write in this skill
— reading/querying the database always goes through G.I.M.L.I., never here.

```bash
sqlite3 "$BRAIN/db/fitness.db" "
CREATE TABLE IF NOT EXISTS activities (
    strava_id      INTEGER PRIMARY KEY,
    date           TEXT    NOT NULL,
    sport_type     TEXT    NOT NULL,
    name           TEXT,
    distance_m     REAL,
    moving_time_s  INTEGER,
    elapsed_time_s INTEGER,
    elevation_m    REAL,
    average_hr     INTEGER,
    max_hr         INTEGER,
    average_cadence REAL,
    average_speed  REAL,
    average_watts  REAL,
    calories       INTEGER,
    suffer_score   INTEGER,
    kilojoules     REAL,
    workout_type   INTEGER,
    synced_at      TEXT    NOT NULL
);
INSERT OR REPLACE INTO activities VALUES (
    <strava_id>,
    '<YYYY-MM-DD>',
    '<sport_type>',
    '<name or NULL>',
    <distance_m or NULL>,
    <moving_time_s or NULL>,
    <elapsed_time_s or NULL>,
    <elevation_m or NULL>,
    <average_hr or NULL>,
    <max_hr or NULL>,
    <average_cadence or NULL>,
    <average_speed or NULL>,
    <average_watts or NULL>,
    <calories or NULL>,
    <suffer_score or NULL>,
    <kilojoules or NULL>,
    <workout_type or NULL>,
    '<now ISO 8601>'
);"
```

`INSERT OR REPLACE` is idempotent — re-running `/daily` for the same Strava ID
overwrites the row, never creates a duplicate. The table is created on first run
and is a no-op on subsequent runs (`IF NOT EXISTS`).

#### HR zone boundaries — first-time save (plan row 6, when triggered)

When step 5b.6 fell through to Strava's configured zones or the Tanaka
estimate (i.e. `body.md` had no `## Heart rate zones` section yet) and the
plan's row 6 was accepted, append this section to
`$BRAIN/core/health/body.md` (mirrors `/update-core`: edit in place, preserve
every other section, bump the file's `date:`):

```markdown
## Heart rate zones
> Source: <Strava-configured | estimated (Tanaka, age-based)> — as of <date>.
> Re-derive if this becomes stale (e.g. after a max-HR test) — edit in place.

| Zone | Min bpm | Max bpm |
|---|---|---|
| Z1 | <min> | <max> |
| Z2 | <min> | <max> |
| Z3 | <min> | <max> |
| Z4 | <min> | <max> |
| Z5 | <min> | <max> |
```
This write happens **at most once** — once the section exists, step 5b.6
always finds it first and the plan never proposes row 6 again. The user can
still hand-edit the section later (e.g. after an updated max-HR test); `/daily`
only ever reads it after that.

### 8. Report

```
── /daily complete — <DATE> (<NEW | UPDATE>) ───────────────────────────
✅ core/health/body.md           updated (measurement log +1 row)
✅ backlog/check/<slug>.md       written
✅ current/context/job-search.md updated
✅ knowledge/notes/<slug>.md     written
✅ knowledge/places/<slug>.md    <new file | visit row added>
✅ knowledge/events/<YYYY-MM-DD>_<slug>.md   written
✅ current/daily/<YYYY-MM>.md    <new section | merged>
✅ current/daily/<YYYY>.md       <new row | row updated>
✅ current/fitness/<YYYY-MM>.md  <new entry | merged> (Strava ID <id>, zones: <source>)
✅ current/fitness/<YYYY>.md     <new month row | row updated>
✅ brain/db/fitness.db           upserted (Strava ID <id>, <sport_type>, <dist> km)
✅ core/health/body.md           HR zones section added (<Strava | estimated>)
⏭️  <item>                        skipped (dropped in edit)
❓ <item>                         left unresolved — not written
⚠️  No matching Strava activity for <DATE> — logged as narrative only
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
  Ambiguous items are flagged and either resolved via the step 5c batch question
  or left unwritten — never guessed.
- **Strava is the source of truth for objective workout stats, never the user's
  typed numbers.** A sport-activity mention triggers a live lookup (step 5b);
  if Strava is unreachable or no activity matches, the item silently falls
  back to narrative-only routing — nothing is lost, the structured
  `current/fitness/` entry just isn't created that run.
- **HR zone boundaries — three-tier fallback, cached after first use.**
  `core/health/body.md` → Strava's configured zones → a generic Tanaka-formula
  estimate (step 5b.6). Whichever source resolves it gets persisted to
  `body.md` once (plan row 6, first run only) so later runs never re-derive it
  — and so historical zone-time entries stay comparable against a stable
  boundary set. The user can hand-edit `body.md` later to correct it.
- **`current/fitness/` mirrors `current/daily/`'s shape, not its trigger.**
  Same no-per-activity-file, append-only-with-merge design — but unlike the
  daily journal (written every run), the fitness files are written only when
  step 5b actually matched a Strava activity. Entries are keyed by Strava
  activity ID (a day can hold more than one activity), not by date.
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
- **fitness.db: write here, read via G.I.M.L.I.** This skill is the designated
  writer for `brain/db/fitness.db` — it holds the only `INSERT OR REPLACE`
  against that table. Any querying of fitness data (totals, trends, comparisons)
  goes through G.I.M.L.I., never through a direct `sqlite3` call inside a skill.
  The split is: skills write structured data, G.I.M.L.I. reads it.
- **G.I.M.L.I. gains fitness queries automatically.** `brain/db/fitness.db` is
  auto-discovered via the `brain/db/*.db` glob in Gimli's registry — no
  configuration change needed. Once at least one activity is synced, queries
  like "how many km did I run in June?" or "compare monthly totals" work
  immediately.
- **Places and events routing (step 5d).** A place visit creates or updates
  `knowledge/places/<slug>.md`; an attended event creates
  `knowledge/events/<YYYY-MM-DD>_<slug>.md`. Schemas live in the respective
  `CLAUDE.md` files. Place files are living documents (one per location,
  accumulates visits); event files are one-per-occurrence. An event with a
  physical venue triggers both writes. Step 5d resolves whether a place file
  already exists before the plan is shown — no surprise new-vs-update in step 7.
- **Place vs event in the routing plan.** Show the target path explicitly so the
  user can see at a glance whether a new file will be created or an existing one
  updated. For a place update, show the existing slug; for a new place or event,
  show the proposed slug and ask in `edit` mode if the user wants to change it.
