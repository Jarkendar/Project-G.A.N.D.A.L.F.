# add-contact

Add a new person to `brain/core/contacts/`. Creates a row in the role index
(`contacts.md`) and, if the contact has meaningful data, a per-person detail file
(`<slug>.md`).

## When to use

- Adding a new person to the contacts directory
- Recording context about someone new after meeting them
- Importing a contact you forgot to include in the initial CSV import

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
  hasn't been initialised. Run `/init-brain` or create it manually."
- Stop.

### 3. Establish the name

If the skill was invoked with an argument (e.g. `/add-contact Jan Kowalski`), use
that as the person's name. Otherwise ask:

> "Jak ma na imię (i nazwisko) ta osoba?"

Call it `$NAME`.

### 4. Generate the slug

Derive `$SLUG` from `$NAME`:
- Lowercase the full name
- Replace spaces with `-`
- Transliterate Polish diacritics: ą→a, ć→c, ę→e, ł→l, ń→n, ó→o, ś→s, ź→z, ż→z
- Remove all remaining non-ASCII characters
- Example: `Żaneta Kowalska` → `zaneta-kowalska`; `Krystian` (no surname) → `krystian`

**Conflict check:** if `$BRAIN/core/contacts/$SLUG.md` already exists, or the index
already has a row with `$NAME`, warn the user and ask whether to:
- Update the existing contact instead (use `/update-core` on the file directly), or
- Use a disambiguated slug (e.g. `jan-kowalski-wujek`).

### 5. Gather contact data

Ask in a single message, grouping related fields:

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
Istniejące grupy: Rodzina | Partner | Przyjaciele | Znajomi — paczka / orlik | ...
Wpisz nazwę grupy lub nową nazwę:
```

Accept free-text group name; reuse exact heading string if matching, otherwise create
a new section.

### 6. Decide on a detail file

A per-person `<slug>.md` is created when **any** of these are true:
- `interests` is non-empty
- `notes` is non-empty
- `birthday` is set AND the group is Rodzina, Partner, or Przyjaciele

If none apply: index-only entry (no file, `Plik` column = `—`).

Confirm the decision with the user before proceeding; they can override either way.

### 7. Prepare changes

**Index row** to append to the correct group table in `contacts.md`:
```
| <$NAME> | <role> | <context or —> | [[<$SLUG>]] or — |
```

If the group doesn't exist yet in the index: append a new section after the last
table:
```markdown
## <Group>

| Imię Nazwisko | Rola | Kontekst | Plik |
|---|---|---|---|
| <$NAME> | <role> | <context or —> | [[<$SLUG>]] or — |
```

**Detail file** template (if applicable):

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
- **Urodziny:** <YYYY-MM-DD>          ← omit if empty
- **Jak się znamy:** <context>         ← omit if empty

## Zainteresowania
<bullet list>                          ← omit section if empty

## Notatki
<notes>                                ← omit section if empty
```

Omit any field or section that has no data.

### 8. Privacy gate — confirm before writing

Show the user:

```
── Proposed write ───────────────────────────────────────────────────────
⚠️  core/contacts/ is PRIVATE. In MVP may enter Claude API context window.

Index:  core/contacts/contacts.md
        + | <$NAME> | <role> | <context> | <[[slug]] or —> |
          (group: <Group>)
```

If a detail file is being created, add:
```
File:   core/contacts/<$SLUG>.md  (new)
```

```
Write? [y / n / edit]
────────────────────────────────────────────────────────────────────────
```

On `edit`: let the user correct the content, then re-show and ask again.

### 9. Write

On `y`:

1. **Edit `contacts.md` in place:** locate the correct group table and append the
   new row at the bottom. Bump `date:` frontmatter to current ISO 8601 datetime.
2. **Write detail file** (if applicable): create `$BRAIN/core/contacts/$SLUG.md`.

On `n`: discard everything, stop.

### 10. Report

```
── Contact added ────────────────────────────────────────────────────────
✅ Index:  core/contacts/contacts.md  (+1 row — group: <Group>)
✅ File:   core/contacts/<$SLUG>.md   (new)    ← if created
────────────────────────────────────────────────────────────────────────
```

---

## Notes

- **Index is the single source of truth for roles.** Never create a detail file
  without a corresponding index row. The index is what Gandalf greps first.
- **Slug uniqueness matters.** If two people share a name, disambiguate the slug
  with a suffix: `jan-kowalski-wujek`, `jan-kowalski-kolega`. Document the
  disambiguation in the `context` column of the index.
- **No invented facts.** Every field must come from the user. Unknown fields stay
  empty — do not fill with assumptions or inferences.
- **Updating existing contacts** (adding new interests, notes, a birthday discovered
  later): use `/update-core` and target `core/contacts/<slug>.md` directly, or
  `/interview` with the person's name as the topic.
- **Privacy.** All contacts are PRIVATE (`core/` scope). Content stays local.
  See `core/contacts/CLAUDE.md` for full privacy rules.
