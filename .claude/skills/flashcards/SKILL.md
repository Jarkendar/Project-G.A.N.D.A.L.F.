---
name: flashcards
description: >-
  Turn what the owner has been learning into Anki flashcards through
  A.R.W.E.N. (the `arwen` MCP server — the owner's Anki collection, synced
  with AnkiDroid through AnkiWeb). Sources: the current chat, notes in
  brain/, archived AI conversations in brain/conversations/, or pasted text.
  Drafts the cards, places them in existing decks, drops duplicates, and
  adds them only after the owner approves. Use when the owner says "zrób mi
  fiszki z …", "fiszki z tej rozmowy", "dodaj to do Anki", "make flashcards
  from …", or after a learning session they want to retain.
---

# flashcards

Makes spaced-repetition cards from material the owner has actually worked
through, and puts them into their Anki collection via A.R.W.E.N. The owner
reviews on AnkiDroid; the cards reach the phone through AnkiWeb.

Cards are for **knowledge** — concepts, facts, terms, APIs, how things work.
Not for speaking practice: in the 2023 plan flashcards did not help English,
because the gap was speaking, not understanding
(`knowledge/career/senior-android-plan-2023-retro.md`). English vocabulary
is fine as cards; speaking belongs to `/english-prep` and live practice.

## When to use

- "zrób mi fiszki z tego, o czym rozmawialiśmy" / "z kursu MCP" / "z notatki o X".
- After reading, a course, a mock interview, or a chat where the owner learned something.
- With pasted text or a topic: "fiszki z tego artykułu", "fiszki o StateFlow".

## Tools

- `mcp__arwen__list_decks` — the owner's decks (syncs from AnkiWeb first).
- `mcp__arwen__find_notes(query)` — Anki search, for duplicates.
- `mcp__arwen__add_notes(cards, allow_new_decks)` — adds approved cards, then syncs.
- Samwise (`mcp__samwise__context` / `search`) and `Read` to gather brain/ material.

If the `arwen` tools are missing, or a tool answers `ARWEN: not logged in`,
stop and tell the owner: run `.claude/scripts/arwen/.venv/bin/python
.claude/scripts/arwen/login.py` in a terminal once. Do not work around it.

---

## Steps

### 1. Gather the material

Work out what the owner means and collect it — do not write cards from memory
of a topic the owner has not studied:

| Source | How |
|---|---|
| This chat | The relevant part of the current conversation. |
| A note or topic in brain/ | `mcp__samwise__context(query)`, then `Read` the files the cards will rest on. |
| An AI conversation | `brain/conversations/` — find it by title/date (`Glob`, Samwise), `Read` it. |
| Pasted text | The text as given. |
| A bare topic ("fiszki o X") | Ask what to base them on; if the owner says "your knowledge", say the cards come from general knowledge, keep them to well-established facts, and tag them `source:general`. |

Note each card's **source**: a brain/ path, `chat`, `conversation:<file>`,
`pasted`, or `general`.

### 2. Mark private material

AnkiWeb is an external service, so every added card leaves the Pi.
A card is **PRIVATE** when it rests on:

- `brain/core/`, `brain/current/` or `brain/conversations/` (PRIVATE folders), or a file with `privacy: private`;
- personal facts from the chat (health, money, people, addresses, work details, credentials).

Private cards are never added silently: they go in a separate section of the
draft and need the owner's explicit yes (step 5). Anything secret —
passwords, keys, account numbers — is never made into a card at all.

### 3. Write the cards

One card, one fact. Rules:

- **Atomic:** a single fact or idea per card. Split lists and multi-part answers into several cards.
- **Self-contained question:** carry enough context that the card makes sense months later, alone ("W Kotlinie: czym różni się `StateFlow` od `SharedFlow`?", not "Czym się różni?").
- **Short answer:** a word, a phrase, or one or two sentences. No yes/no questions.
- **Card types:**
  - `basic` — question → answer; the default.
  - `reversed` — both directions; only for term ↔ definition and vocabulary.
  - `cloze` — a sentence with `{{c1::…}}` deletions; good for definitions and exact phrasing. Use `{{c2::…}}` for a second, separately-tested gap.
- **Code** in backticks, line breaks allowed; no HTML, no images.
- **Language:** the language of the material; keep established English terms as they are.
- **Priorities:** what the owner struggled with, got wrong, or asked about twice first; skip what is trivial for them.
- **Volume:** usually 5–20 cards per session; more only when the material warrants it and the owner asked for thoroughness.

### 4. Place and deduplicate

1. `mcp__arwen__list_decks` — put each card in the deck that fits best. Propose a new deck (full `Parent::Child` name) only when none fits, and mark it as new.
2. `mcp__arwen__find_notes` with the key term of each card (e.g. `StateFlow`, `"deck:Android*" coroutine`). A card whose fact is already there is dropped from the draft and listed under "already in Anki".

### 5. Show the draft and wait

```
**Fiszki — szkic** (źródło: <sources>)

| # | talia | typ | przód | tył | źródło |
|---|---|---|---|---|---|
| 1 | Android::Kotlin | basic | … | … | chat |

**Prywatne — dodać do AnkiWeb?** (tylko po wyraźnym „tak”)
| # | … |

**Nowe talie:** <name> — for cards #…
**Już są w Anki (pominięte):** …

Napisz „ok”, poprawki (np. „3: tył = …”, „usuń 5”) albo „bez prywatnych”.
```

Apply the owner's edits and show the changed rows again if the changes were substantial. **Nothing is added before the owner approves.**

### 6. Add

`mcp__arwen__add_notes` with the approved cards (≤ 50 per call):

- `tags`: `source:<source>` (paths with `/`, e.g. `source:brain/knowledge/tech/mcp.md`) and a topic tag (`kotlin`, `mcp`, …). A.R.W.E.N. adds `gandalf` itself.
- `allow_new_decks: true` only if the owner approved the new decks.
- Private cards only if the owner said yes to them.

Report what came back: added, skipped as duplicates, and the sync status.
If a tool answers `ARWEN: …` (a sync refused, a missing deck), relay it as
is and stop — never retry a refused sync or try to force one.

### 7. Done

Tell the owner the cards are on AnkiWeb and will appear on AnkiDroid after
its next sync. The skill writes nothing to brain/.

---

## Rules

- No card is added without the owner's approval of the draft.
- Private material reaches AnkiWeb only with the owner's explicit yes, per batch.
- Cards come from the gathered material, not from invention; general knowledge only when the owner asked for it, tagged `source:general`.
- A.R.W.E.N. never does a full upload; do not look for ways around a refused sync.
