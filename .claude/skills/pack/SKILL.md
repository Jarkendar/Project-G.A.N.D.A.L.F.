---
name: pack
description: >-
  Build a packing list for a specific trip from the item catalogue in
  brain/knowledge/travel/packing/ and the per-person packing profiles in
  brain/core/travel/packing/ — a pre-filled table with one column per traveller
  for personal items, plus a separate section for shared items carried once.
  Use this skill when packing for any trip (holiday, business delegation, city
  break, mountains, festival, race), when a trip involves more than one person
  and the list must account for their individual needs, when reviewing what was
  actually used after coming back so the catalogue learns, or when adding items
  and conditions to the catalogue or to someone's packing profile.
---

# pack

Generate a packing list for **one concrete trip** — not a generic checklist.
The list is derived by filtering a shared item catalogue through the trip's
conditions (transport, season, purpose, nights, accommodation), then splitting
it into **personal** items (each traveller packs their own) and **shared** items
(one person carries it for everyone).

Data model has three axes:

| Axis | Values | Purpose |
|---|---|---|
| **priority** | `must` / `base` / `extra` | how bad it is to forget it |
| **when** | condition tags, empty = always | whether it applies to *this* trip |
| **group** | dokumenty, elektronika, higiena, leki, ubrania, sprzęt, jedzenie, inne | how the printed list is grouped |

`priority` and `when` are independent: a passport is `must` **and** conditional
(`dest:non-eu`). Never collapse them into one category.

**The catalogue is a pool of candidate items, not an inventory.** An entry says the
thing *can* be needed on some trip — it says nothing about anyone owning it. Ownership
lives per person, in the profiles (`ma:` / `nie ma:`), and is unknown until stated.
Never infer possession from an item's presence in the catalogue, nor from an old
packing list.

## When to use

- Packing for any trip, alone or with other people.
- A trip where different travellers need different things (partner, friends, family).
- After a trip: recording what was missing or never used, so the catalogue improves.
- Adding a new item, condition, or person profile to the packing data.

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist:
- Tell the user: "`.claude/gandalf.env` not found. Copy `.claude/gandalf.env.example`
  to `.claude/gandalf.env` and set `BRAIN_PATH` to the path of your brain/ repo."
- Stop.

Resolve the path (expand `~`, resolve relative paths from the project root).
Call it `$BRAIN`. If `$BRAIN` does not exist, tell the user to run `/init-brain` and stop.

Data locations:

| Path | Privacy | Contents |
|---|---|---|
| `$BRAIN/knowledge/travel/packing/catalogue.md` | public | the item catalogue |
| `$BRAIN/knowledge/travel/packing/trip-types.md` | public | trip presets → condition sets |
| `$BRAIN/core/travel/packing/<slug>.md` | **private** | per-person profiles |
| `$BRAIN/current/trips/YYYY-MM-DD_<slug>.md` | **private** | generated trip lists |

If `catalogue.md` does not exist, say so and offer to create it from the skeleton in
**Appendix A**. Proceed only after confirmation.

### 2. Determine mode

- `/pack <trip description>` → **Mode A: generate** (default).
- `/pack` (no argument) → ask "Dokąd i kiedy?" then Mode A.
- `/pack review [<trip>]` → **Mode B: post-trip review**.
- `/pack catalogue` / `/pack profile <person>` → **Mode C: edit data**.

---

## Mode A — Generate a trip list

### A1. Collect trip parameters

Ask for everything missing **in one message**, not one question at a time. Never
ask about something the user already stated.

```
── Wyjazd ───────────────────────────────────────────────
Dokąd:        <miasto / kraj>
Kiedy:        <daty> (<N nocy>)
Cel:          <urlop | delegacja | city break | góry | morze | festiwal | zawody>
Transport:    <samolot | auto | pociąg | autobus | rower>
Nocleg:       <hotel | apartament | namiot | rodzina | hostel>
Kto jedzie:   <osoby>
Aktywności:   <bieganie | pływanie | wędrówki | kajak | rower | brak>
─────────────────────────────────────────────────────────
```

If a **trip type preset** in `trip-types.md` matches (e.g. "delegacja"), load its
condition set as the default and show which conditions it filled in — the user only
corrects what differs.

**Weather:** do not guess. If the season matters and the user has not said, ask for
the expected temperature range in one line. Do not make network calls.

### A2. Build the condition set

Translate the parameters into condition tags. Vocabulary (extend as needed, but
reuse existing tags before inventing new ones — check the catalogue first):

| Key | Values |
|---|---|
| `dest:` | `pl`, `eu`, `non-eu` |
| `transport:` | `plane`, `car`, `train`, `bus`, `bike` |
| `purpose:` | `work`, `leisure`, `city`, `mountains`, `sea`, `camping`, `festival`, `race` |
| `season:` | `winter`, `summer`, `shoulder` |
| `weather:` | `rain`, `heat`, `frost` |
| `nights:` | `0`, `1-3`, `4-7`, `8+` |
| `stay:` | `hotel`, `apartment`, `tent`, `family`, `hostel` |
| `activity:` | `running`, `swimming`, `hiking`, `kayak`, `cycling`, `gym`, `photo` |
| `company:` | `solo`, `partner`, `friends`, `family` |

**Matching rules:**
- Item with empty `when` → **always** included.
- Multiple conditions in `when`, comma-separated → **AND** (all must hold).
- Alternatives inside one value with `|` → **OR** (`purpose:sea|camping`).
- A condition the trip parameters do not cover (unknown, not asked) → treat as **not
  matching**, but list the item in "Pominięte warunkowe" at the end of A5 so nothing
  disappears silently.

### A3. Resolve the travellers

For each person named:

1. Look for `$BRAIN/core/travel/packing/<slug>.md`.
2. If missing, grep `$BRAIN/core/contacts/contacts.md` for the person to get the
   canonical slug, then check again.
3. Still missing → offer to create a minimal profile now (Mode C), or continue
   without one using catalogue defaults. Say explicitly which you did.

A profile contributes:
- **extra items** the person always takes (their own meds, contact lenses, cosmetics),
- **exclusions** — catalogue items this person never takes,
- **possession** — what they own (`ma:`) and what they demonstrably don't (`nie ma:`),
- **quantities** — e.g. `koszulki: nights + 1`,
- **notes** — habits worth a reminder ("ładuje powerbank dzień wcześniej").

Profiles start **empty** and fill up from actual trips (Mode B) and from what the user
says. Do not backfill a profile from a historical packing list — a tick in an old sheet
means "took it that time", not "owns it" or "always takes it".

Profiles are PRIVATE. Read them into the working context, but never copy medical or
health details into the public catalogue.

### A4. Split personal vs shared

Every catalogue item has `scope`:

- `personal` — **each traveller packs their own** (ID, paszport, bielizna, szczoteczka,
  leki). Gets one column per person in the table.
- `shared` — **one copy for the whole trip** (ładowarka, apteczka, adapter, głośnik).
  Goes to the separate "Wspólne" section with a `Kto pakuje` column.

When only one person travels, still keep the two sections — shared collapses to
"co idzie do wspólnej torby" and stays useful.

**Assignment of shared items:** propose the owner from profiles (who owns the thing,
who took it last trip). If unknown, leave `Kto pakuje` empty rather than guessing.

### A5. Compose the list — pre-filled

The table is **pre-filled**, not blank: mark `x` for every person the item applies to,
based on catalogue `scope`, the person's profile, and the conditions. The user's job is
to correct, not to fill it in.

```markdown
# Pakowanie — <Miasto> <YYYY-MM-DD>

<Cel> · <N nocy> · <transport> · <nocleg> · <pogoda>
Jadą: <osoby>

## Wspólne (jedna sztuka na wyjazd)

| Rzecz | Prio | Kto pakuje | ✓ |
|---|---|---|---|
| ładowarka USB-C 65W | must | Jarek | ☐ |
| apteczka podręczna | base | Ania | ☐ |

## Osobiste

### Dokumenty
| Rzecz | Prio | Jarek | Ania |
|---|---|---|---|
| ID | must | x | x |
| paszport | must | x | x |

### Elektronika
| Rzecz | Prio | Jarek | Ania |
|---|---|---|---|
| powerbank | base | x | |

### Higiena
...

## Do zdobycia przed wyjazdem
Potrzebne na ten wyjazd, a nie wiadomo, czy ktoś to ma — kupić, pożyczyć albo odhaczyć „mam":
| Rzecz | Prio | Dla kogo | Status |
|---|---|---|---|
| adapter gniazdka UK | must | wspólne | ? |

## Pominięte warunkowe
Rzeczy z katalogu, których warunek nie zadziałał przy tym wyjeździe — sprawdź, czy słusznie:
- strój kąpielowy — `purpose:sea|stay:hotel-pool`
- czołówka — `activity:hiking`

## Po powrocie
- Czego zabrakło:
- Czego nie użyłem:
```

Rules for the rendering:
- One table per `group`; skip groups with no items.
- Column order: `must` first, then `base`, then `extra`, alphabetical inside a priority.
- Person columns in the order the user listed them.
- Personal item that applies to only one traveller still gets a row — empty cell for the rest.
- Quantities from profiles go in the item cell: `koszulki ×4`.
- Keep it scannable on a phone: no more than 4 person columns; beyond that, split the
  table per person and say why.
- **Possession**: an item still goes into the main table — it is what's needed, regardless
  of who owns it. Additionally, list it under "Do zdobycia" when the profile says
  `nie ma:` (status `brak`) or says nothing at all (status `?`). Items marked `ma:` never
  appear there. Do not silently drop a needed item because nobody owns it.

### A6. Gate before writing

```
── Proposed write ───────────────────────────────────────
File:    $BRAIN/current/trips/<YYYY-MM-DD>_<slug>.md
Mode:    new file | update existing
Items:   <N osobistych> + <M wspólnych>, <K pominiętych warunkowych>
Privacy: private
─────────────────────────────────────────────────────────
⚠️  current/ is PRIVATE — stays on this machine. In the MVP it may
    enter the Claude API context window (see IMPLEMENTATION.md §
    "Privacy in the Claude-API MVP"). Phase 2 closes this exception.
─────────────────────────────────────────────────────────
Write this? [y / n / edit]
```

- **y** → write.
- **edit** → apply corrections (add/remove items, flip cells, reassign shared owner),
  re-show, ask again.
- **n** → discard, stop.

If the file already exists (re-running for the same trip), **merge**: keep the user's
`✓` marks and manual additions, add only new rows, and report what changed. Never
overwrite a list that already has ticks.

### A7. Write and report

Frontmatter for the trip file:

```yaml
---
date: <YYYY-MM-DDTHH:MM:SS>
source: pack
privacy: private
status: active
type: packing-list
trip: "<Miasto> <YYYY-MM-DD>"
date_start: YYYY-MM-DD
date_end: YYYY-MM-DD
people: [jarek, ania-marciniak]
conditions: [purpose:city, transport:plane, nights:1-3, stay:hotel, season:shoulder]
tags: [travel, packing, <city-slug>, <YYYY>]
title: "Pakowanie — <Miasto> <YYYY-MM-DD>"
---
```

Report:

```
── Lista gotowa ──────────────────────────────────────────
✅ Written: $BRAIN/current/trips/<YYYY-MM-DD>_<slug>.md
   Osobiste: <N> pozycji × <P> osób
   Wspólne:  <M> pozycji
   Pominięte warunkowe: <K>
──────────────────────────────────────────────────────────
Po powrocie: `/pack review <slug>` — dopisze do katalogu, czego zabrakło.
```

---

## Mode B — Post-trip review

The feedback loop. Without it the catalogue never improves.

1. Read the trip file. Ask two questions: **czego zabrakło?** and **czego nie użyłeś?**
2. For each missing item: propose a catalogue entry (group, priority, scope, `when`
   derived from that trip's conditions). Confirm, then append to `catalogue.md`.
3. For each unused item: do **not** delete it. Propose one of:
   - demote priority (`must` → `base` → `extra`),
   - narrow it with a condition (`when: season:winter`),
   - move it to a person's profile exclusions.
4. For each item from "Do zdobycia": ask whether it was bought/borrowed, and record the
   answer in the person's `Posiada` table (or as shared gear). This is the main way
   possession data accumulates.
5. Update the trip file's `status: done` and fill the "Po powrocie" section.
6. Show a single gate for all catalogue/profile edits, then write.

Append-only spirit: items are demoted or narrowed, never removed from history.

---

## Mode C — Edit catalogue / profiles

- `/pack catalogue` — print the catalogue grouped by `group`, then accept edits:
  add item, change priority, add/remove condition, change scope.
- `/pack profile <person>` — print that person's profile, then accept edits: extra
  items, exclusions, quantities, notes. Creates the file if missing.

Every write goes through the same gate as A6. Person profiles carry
`privacy: private` and live in `core/` — never move their content into the catalogue.

---

## Appendix A — File formats

### catalogue.md

Public, generic, person-agnostic. One markdown table per group:

```markdown
### elektronika

| Rzecz | Prio | Scope | When | Uwagi |
|---|---|---|---|---|
| ładowarka USB-C | must | shared | | 65W, do laptopa i telefonu |
| powerbank | base | personal | | |
| adapter gniazdka | must | shared | dest:non-eu | UK/CH mają inne gniazdka |
| czołówka | base | personal | activity:hiking\|stay:tent | |
```

Empty `When` = always applies. `\|` escapes the OR separator inside a table cell.

### core/travel/packing/&lt;slug&gt;.md

Private, one file per person:

```markdown
---
date: <YYYY-MM-DDTHH:MM:SS>
source: pack
privacy: private
status: active
type: packing-profile
person: <slug>
tags: [travel, packing, <slug>]
title: "Profil pakowania — <Imię>"
---

# Profil pakowania — <Imię>

## Zawsze zabiera (poza katalogiem)
| Rzecz | Prio | Grupa | When | Uwagi |
|---|---|---|---|---|

## Nie zabiera (wyjątki od katalogu)
| Rzecz | Powód |
|---|---|

## Posiada
| Rzecz | Ma | Uwagi |
|---|---|---|
| powerbank | tak | 20 000 mAh |
| walizka kabinowa | nie | pożycza od rodziców |

Brak wiersza = nie wiadomo. Nie zgaduj — brak wiedzy trafia do "Do zdobycia" ze
statusem `?`.

## Ilości
| Rzecz | Reguła |
|---|---|
| koszulki | nights + 1 |

## Nawyki
- <jedna linia na nawyk>
```

---

## Notes

- **Katalog jest wspólny, profile są osobiste.** Rzecz, którą bierze każdy — do
  katalogu. Rzecz specyficzna dla osoby (leki, soczewki, kosmetyki) — do profilu
  w `core/`. Danych zdrowotnych nigdy nie przenoś do `knowledge/`.
- **Nie zgaduj pogody ani warunków** — pytaj. Brak danych to nie to samo co "nie dotyczy";
  taka rzecz ląduje w "Pominięte warunkowe", nie znika.
- **Nie wymyślaj rzeczy**, których nie ma w katalogu ani w profilu. Możesz je
  *zaproponować* jako osobną, oznaczoną listę — użytkownik decyduje, czy wchodzą.
- **Katalog ≠ inwentarz.** Pozycja w katalogu nie znaczy, że ktokolwiek to ma. Stara
  lista pakowania z konkretnego wyjazdu nie jest źródłem wiedzy o posiadaniu ani o
  stałych nawykach — mówi tylko, co ktoś wtedy wziął.
- **Lista jest wstępnie wypełniona.** Pusta tabela do odhaczenia to porażka tego skilla.
- **Wyjazd po fakcie** trafia do `knowledge/events/` przez `/daily` — ten skill nie
  tworzy wpisów o wydarzeniach, tylko listy pakowania w `current/trips/`.
- **Nie dotyka `_meta/`** — queue.jsonl i manifest.json to teren Bilbo / Treebeard.
