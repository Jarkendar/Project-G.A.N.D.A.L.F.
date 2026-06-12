# add-contact

Add a new person to `brain/core/contacts/`, or update an existing one.

- **Add mode** (default): creates an index row and optionally a per-person detail file.
- **Update mode** (auto-triggered when person already exists): edits the index row and/or
  detail file in place; can also promote an index-only contact to a full detail file.

## When to use

- Adding a new person after meeting them
- Importing a contact forgotten in the initial bulk import
- Updating an existing contact — adding interests, notes, a birthday, fixing role
- Promoting an index-only entry to a full per-person file

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist:
- Tell the user: "`.claude/gandalf.env` not found. Copy `.claude/gandalf.env.example`
  and set `BRAIN_PATH`."
- Stop.

Resolve the path (expand `~`, resolve relative paths from project root). Call it `$BRAIN`.

### 2. Verify contacts structure

Check that `$BRAIN/core/contacts/contacts.md` exists.

If missing:
- Tell the user: "`core/contacts/contacts.md` not found. The contacts structure
  hasn't been initialised."
- Stop.

### 3. Establish the name

If the skill was invoked with an argument (e.g. `/add-contact Jan Kowalski`), use
that as the person's name. Otherwise ask:

> "Jak ma na imię (i nazwisko) ta osoba?"

Call it `$NAME`.

### 4. Generate slug + detect mode

Derive `$SLUG` from `$NAME`:
- Lowercase the full name
- Replace spaces with `-`
- Transliterate Polish diacritics: ą→a, ć→c, ę→e, ł→l, ń→n, ó→o, ś→s, ź→z, ż→z
- Remove all remaining non-ASCII characters
- Example: `Żaneta Kowalska` → `zaneta-kowalska`; `Krystian` (no surname) → `krystian`

**Mode detection** — check both signals:

```bash
grep -i "$NAME" "$BRAIN/core/contacts/contacts.md"   # → $IN_INDEX
test -f "$BRAIN/core/contacts/$SLUG.md"               # → $HAS_FILE
```

| `$IN_INDEX` | `$HAS_FILE` | Mode |
|---|---|---|
| false | false | **Add** — new contact |
| true | false | **Update** — index-only contact (promotion candidate) |
| false | true | **Update** — file exists, index row missing (edge case; fix both) |
| true | true | **Update** — full existing contact |

Tell the user which mode is active before proceeding.

---

## Add mode (steps 5A–9A)

### 5A. Gather contact data

Ask in a single message:

```
Podaj dane dla: <$NAME>

Wymagane:
- Rola / relacja (np. Przyjaciel, Kolega z pracy, Kuzyn):
- Grupa w indeksie (patrz niżej):

Opcjonalne:
- Kontekst (1 linia — jak się znacie / co robi):
- Urodziny (DD.MM.RRRR lub RRRR-MM-DD):
- Zainteresowania (przecinek-oddzielone):
- Notatki (dowolny tekst):
```

**Show existing groups** by reading the `## ` headings from `contacts.md`:
```
Istniejące grupy: Rodzina | Partner | Przyjaciele | ...
Wpisz nazwę grupy lub nową nazwę:
```

Accept free-text; reuse exact heading string if it matches, otherwise create a new section.

### 6A. Decide on a detail file

Create `<slug>.md` when **any** of these are true:
- `interests` is non-empty
- `notes` is non-empty
- `birthday` is set AND group is Rodzina, Partner, or Przyjaciele

Otherwise: index-only entry (`Plik` = `—`). Confirm the decision; user can override.

### 7A. Prepare changes

**Index row:**
```
| <$NAME> | <role> | <context or —> | [[<$SLUG>]] or — |
```
Append to the bottom of the matching group table. If group doesn't exist, append a new
`## <Group>` section with table header and row after the last existing section.

**Detail file** (if applicable):
```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: manual
privacy: private
status: active
tags: [contacts, <role-slug>]
title: "<$NAME> — <role>"
---

# <$NAME>

- **Rola:** <role>
- **Urodziny:** <YYYY-MM-DD>        ← omit if empty
- **Jak się znamy:** <context>       ← omit if empty

## Zainteresowania
<bullet list>                        ← omit section if empty

## Notatki
<notes>                              ← omit section if empty
```

### 8A. Privacy gate

```
── Proposed write ───────────────────────────────────────────────────────
⚠️  core/contacts/ is PRIVATE. In MVP may enter Claude API context window.

Index:  core/contacts/contacts.md
        + | <$NAME> | <role> | <context> | <[[slug]] or —> |
          (group: <Group>)
[File:  core/contacts/<$SLUG>.md  (new)]    ← if applicable
────────────────────────────────────────────────────────────────────────
Write? [y / n / edit]
```

### 9A. Write & report

On `y`:
1. Edit `contacts.md` — append new row, bump `date:`.
2. Write `<slug>.md` if applicable.

```
── Contact added ────────────────────────────────────────────────────────
✅ Index:  core/contacts/contacts.md  (+1 row — group: <Group>)
✅ File:   core/contacts/<$SLUG>.md   (new)    ← if created
────────────────────────────────────────────────────────────────────────
```

---

## Update mode (steps 5U–9U)

### 5U. Show current state

Read `contacts.md` and extract the existing index row for `$NAME` (group, role, context,
whether file exists). If `$HAS_FILE=true`, read the detail file too.

Display a summary before asking anything:

```
── Aktualny stan: <$NAME> ──────────────────────────────────────────────
Grupa:      <Group>
Indeks:     <role> | <context or —> | <[[slug]] or —>
```
If file exists, continue:
```
Plik:       core/contacts/<$SLUG>.md
  Urodziny:      <value or —>
  Zainteresowania: <list or —>
  Notatki:       <text or —>
────────────────────────────────────────────────────────────────────────
```

### 6U. Gather changes

Ask which fields to update (number-based, supports multi-select):

```
Co chcesz zmienić? (wpisz numery, np. 1,3 lub 'all')

1. Rola lub kontekst w indeksie
2. Urodziny
3. Zainteresowania (dodaj do listy)
4. Notatki (dopisz)
```

If `$HAS_FILE=false` (index-only contact), add:
```
5. Awansuj na pełny wpis — stwórz plik core/contacts/<$SLUG>.md
```

Ask only about selected fields. For fields that already have a value:
- **Interests** — default: append new items; say "replace" to overwrite
- **Notes** — default: append new paragraph; say "replace" to overwrite
- **Role, context, birthday** — default: replace; show old value first

### 7U. Promotion (index-only → detail file)

If option 5 selected, or if `$HAS_FILE=false` and user provides interests/notes/birthday:
- Gather any missing fields not already collected in step 6U
- Prepare new `<slug>.md` from template (same as step 7A)
- Update the index row: change `—` in Plik column to `[[<$SLUG>]]`

### 8U. Privacy gate

```
── Proposed changes ─────────────────────────────────────────────────────
⚠️  core/contacts/ is PRIVATE. In MVP may enter Claude API context window.

Index:  core/contacts/contacts.md
        ~ | <$NAME> | <new role> | <new context> | ...   ← if changed
          (no index change)                               ← if unchanged
```
If file changed/created:
```
File:   core/contacts/<$SLUG>.md
        ~ Urodziny: <old> → <new>                        ← replaced field
        + Zainteresowania: <added items>                 ← appended
        + Notatki: <added text>                          ← appended
[File:  core/contacts/<$SLUG>.md  (new — promoted)]     ← if promotion
```
```
Write? [y / n / edit]
────────────────────────────────────────────────────────────────────────
```

### 9U. Write & report

On `y`:
1. **Index changed** — edit the specific row in `contacts.md`, bump `date:`.
2. **File changed** — edit `<slug>.md` in place (append or replace as agreed), bump `date:`.
3. **Promotion** — write new `<slug>.md`, update index row Plik column `—` → `[[<slug>]]`.

```
── Contact updated ──────────────────────────────────────────────────────
✅ Index:  core/contacts/contacts.md  (row updated)   ← if changed
✅ File:   core/contacts/<$SLUG>.md   (updated)        ← if changed
✅ File:   core/contacts/<$SLUG>.md   (created)        ← if promoted
────────────────────────────────────────────────────────────────────────
```

---

## Notes

- **Index is the single source of truth for roles.** Never create a detail file
  without a corresponding index row. The index is what Gandalf greps first.
- **Slug uniqueness.** Two people with the same name need disambiguation:
  `jan-kowalski-wujek`, `jan-kowalski-kolega`. Document the suffix in the
  `context` column.
- **No invented facts.** Every field must come from the user. Unknown fields stay
  empty.
- **Append vs replace.** Interests and notes default to append — existing data is
  never silently overwritten. The user must explicitly say "replace" to overwrite.
- **Privacy.** All contacts are PRIVATE (`core/` scope). Content stays local.
  See `core/contacts/CLAUDE.md` for full privacy rules.
