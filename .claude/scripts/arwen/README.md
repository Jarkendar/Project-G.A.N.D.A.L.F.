# A.R.W.E.N. — Anki Repetition & Web-sync Engine for Notes

Flashcards into the owner's Anki collection, as MCP tools. The owner reviews
on AnkiDroid; A.R.W.E.N. reaches it through AnkiWeb. The `/flashcards` skill
(`.claude/skills/flashcards/`) decides what goes in; A.R.W.E.N. only stores
and syncs.

## How it reaches the phone

AnkiDroid has no API reachable from outside the phone, so the Pi keeps its
own copy of the collection with the official `anki` library (the engine of
Anki desktop, no GUI) and syncs it with AnkiWeb around every write:

- **incremental sync** — always; it merges both sides;
- **full download** (AnkiWeb → Pi) — only while the Pi holds nothing
  unsynced; a `dirty` flag in `state.json` spans every write until the sync
  after it succeeds;
- **full upload** (Pi → AnkiWeb) — **never**: it would overwrite the reviews
  made on the phone. When AnkiWeb asks for one, the tools stop and explain.

Ready-made servers were weighed first (2026-09-26): the popular ones
(ankimcp, AnkiConnect-based) need Anki desktop running — on a Pi without a
screen that means Qt under a virtual display, system packages and a sync
dialog nobody can click; the headless `anki-sync-mcp` had no users yet and
would hold the AnkiWeb password. Four tools on the official library were
the smaller risk.

## Tools

| tool | does |
|---|---|
| `list_decks` | syncs, then lists decks with note counts |
| `find_notes(query, limit)` | Anki search over the Pi's copy — duplicate checks |
| `add_notes(cards, allow_new_decks)` | syncs, adds (≤ 50; `basic`, `reversed`, `cloze`), syncs again; skips duplicates, refuses unknown decks unless allowed |
| `sync` | an incremental sync now |

Note types are found by their stock kind, not their name, so a localized
AnkiDroid collection ("Podstawowy", "Luka") works. Every card is tagged
`gandalf`. Text is escaped; `` `code` `` and line breaks survive.

## Setup

```bash
python3 -m venv .claude/scripts/arwen/.venv
.claude/scripts/arwen/.venv/bin/pip install -r .claude/scripts/arwen/requirements.txt
# once, in a terminal: asks for the AnkiWeb e-mail and password, stores only
# the session key (mode 600), then downloads the collection
.claude/scripts/arwen/.venv/bin/python .claude/scripts/arwen/login.py
```

Registered as `arwen` in `.mcp.json` (stdio). Data lives outside the repos
in `~/.local/share/gandalf/arwen/` (`ARWEN_DIR` overrides): `collection.anki2`,
`auth.json` (session key), `state.json`. Each call opens the collection under
a file lock and closes it, so two sessions never hold it open together, and
nothing stays in memory between calls.

## Privacy

AnkiWeb is an external service. Cards drawn from PRIVATE brain/ folders
(`core/`, `current/`, `conversations/`) are added only after the owner's
explicit yes for that batch — the skill asks; the server itself does not
know where a card came from.
