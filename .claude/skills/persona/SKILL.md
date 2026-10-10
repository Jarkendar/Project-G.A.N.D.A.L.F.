---
name: persona
description: >-
  Mírdain — build a White Council persona card for a real person, end to end:
  scope, source catalogue, digests in batches, the core card, the behaviour
  validation, upkeep. Writes to brain/knowledge/personas/<slug>/ and drives
  the scripts in .claude/scripts/personas/. Use when the owner says "zrób
  personę", "kolejna persona", "zbuduj personę <kto>", "dodaj <kogoś> do
  Rady", "/persona", or to rework an existing card ("karta v2", "popraw
  personę", "re-walidacja").
---

# persona — Mírdain, the jewel-smiths

A persona card is a person's **way of reaching a decision** — approach,
character, stable views — distilled from their own words. It is not an
encyclopedia of their life and not a quote machine. Every claim in the
card traces back to a digest, every digest to an original.

The process below was learned on seven personas (Buffett, Marks, Bogle,
Taleb, Dalio, Lynch, Housel). Each lesson is in the step where it bites.
The design rationale lives in IMPLEMENTATION.md, Step 6 "Building a
persona"; the scripts in `.claude/scripts/personas/README.md`.

## Ground rules

- **Pace is the owner's.** Steps 1, 2 and 4 end with the owner's
  approval. Digests go in batches, each approved — unless the owner says
  to run all batches ("lecisz ze wszystkimi"); then go on without asking.
- **Where things go.** brain/: commit and push on `main`, adding only the
  paths you wrote. This repo: a branch `feat/persona-<slug>` for the
  IMPLEMENTATION.md entry. The owner merges.
- **Digests and the card are in Polish.** Quotes stay in the original
  language (for a Polish persona, Polish).
- **Keep the edges.** A persona that irritates the owner is doing its
  job — the council exists to pull him out of his bubble. Tone down style,
  never the reasoning or the uncomfortable views.
- **Nothing from memory.** Biography, figures, dates, episodes: only what
  a digest holds. The first Dalio card had a degree and a founding year
  from the model's memory; one was wrong.

## 0. Setup

1. Resolve `BRAIN_PATH` from `.claude/gandalf.env`. Read
   `$BRAIN_PATH/knowledge/personas/CLAUDE.md` if present, and the
   frontmatter (`categories`, `useful_for`, `not_for`) of every existing
   `persona.md` — the new voice must add contrast to that pool.
2. Create the branch `feat/persona-<slug>` off `main` here.
3. Work files (texts to read, drafts) go to the session scratchpad, never
   into brain/ or this repo.

## 1. Scope

Write the scope into the top of `sources.md` (section `## Zakres`):

- **Why this person:** which question the council cannot answer well
  today, and the contrast with each existing persona in one line.
- **Categories, `useful_for`, `not_for`** — `not_for` names the better
  persona where one exists ("lepiej Buffett").
- **Default era** of the voice and the views they abandoned (to be
  confirmed by the digests).
- **What sources exist:** their own writing and speech first (letters,
  essays, memos, blogs, transcripts of talks or podcasts); one or two
  critical reviews as material for blind spots. Books under copyright:
  never stored; their theses come through the essays or talks they grew
  out of.

**Gate:** the owner approves the scope.

## 2. Source catalogue

1. Build the source list: `$BRAIN_PATH/knowledge/personas/<slug>/sources.json`
   (`id` = `<date>-<slug-of-title>`, `url`, `title`, `source_type`,
   `source_date`, `tags`; excerpts of a long file via `from` / `start` /
   `end` — see the docstring of `fetch.py`).
2. `fetch.py <slug> --wayback` downloads, extracts text, records sha256
   and words; `--table` prints the `sources.md` rows.
3. Write `sources.md`: scope, totals (sources, words, years), batches
   (chronological, ~10–17 sources or ~50–60k words each), **gaps** (what
   exists but is unreachable — paywall, 404, video without transcript —
   and what was left out on purpose).
4. Exclude what is not their voice: texts by co-authors or ghost-writers
   presented as theirs, pieces that are mostly other people's words, and
   critical reviews (those are kept, but marked as criticism).
5. Commit and push in brain.

Size: aim for the whole span of their public thinking, not a sample of
one period. The first Taleb catalogue (150k words) was rejected by the
owner as too thin; 250k+ worked.

**Gate:** the owner approves the catalogue (and may add sources).

## 3. Digests, batch by batch

**Default engine: Antigravity CLI (Gemini), not a Claude sub-agent.** Drafts
come from `agy_digest.py`, which runs one headless `agy` call per source in
parallel and spends the Gemini quota instead of the Claude one:

```
python3 .claude/scripts/personas/agy_digest.py <slug> <drafts> <id,...> --surname <Surname>
```

- It replaces steps 1–2 below; step 3 (`assemble.py`) and the quote check
  are unchanged. Model: `gemini-3.8-flash-low` (medium/high cost 3–6x the
  time for no measurable gain). `--jobs 4` is safe; a 429 is retried.
- Only **public** persona sources go to `agy` — it is an external API.
  Never anything from `brain/core/` or `current/`.
- It needs `~/.gemini/antigravity-cli/settings.json` with the tool
  permissions denied (see `agy_digest.py`); if `agy` asks to log in again,
  the owner runs `! agy` once.
- Fall back to the manual steps below for a source that comes back
  `too-large` (> ~110 KB: split it into excerpts first), for an `agy`
  error, and for any source in a language other than Polish or English.
- Gemini sees one source at a time, so *"Zmiana względem wcześniejszych
  lat"* is written as "Brak porównania — źródło digestowane osobno". Leave
  it, or fill it in from the digests you have actually read; the card step
  compares digests anyway.
- Spot-check 2–3 drafts of the batch against their sources before
  `--write` (a wrong fact passes the quote check). Quote misses: fix the
  draft, never the checker.

Manual path — for each source in the batch:

1. `reflow.py <slug> <id>` → the text, one paragraph per line. Read the
   **whole** source. Do not filter it with line-based grep — that cuts
   paragraphs. PDF text: ligatures (ﬁ, ﬀ) and end-of-line hyphenation —
   quote fragments that avoid them.
2. Write the draft into the scratchpad (`<drafts>/<id>.md`), following
   [references/digest.md](references/digest.md).
3. `assemble.py <slug> <drafts> <id,...> --write` — checks every quote
   verbatim against the source, adds frontmatter, writes `sources/`,
   flips `todo` → `esencja` in `sources.md`. A miss: fix the quote, never
   the checker.
4. After the batch: `verify_quotes.py <slug>`, commit and push in brain
   (`feat(personas): <slug> digests P<n>`). The post-commit hook reindexes
   the persona RAG on its own.

Rules that each cost a rework once:
- **Quotes: 0–2, the person's own words, and only when the line is the
  crux.** Not the people they quote, not proverbs, not lines from a
  co-written text. Read the surrounding text before quoting.
- **"Zmiana względem wcześniejszych lat"** refers only to sources you
  have actually read in this process — no "they come back to this later".
- A source that repeats a thesis: note the repetition instead of
  restating it — frequency of a theme says more about style than about
  certainty.
- A date that is approximate gets a note in the digest.

Report per batch: sources done, quotes checked, anything doubtful.

## 4. Core card

Write `persona.md` **only from the digests** (search them; do not re-read
originals), following [references/card.md](references/card.md). Then
show the owner the card's key sections — how it decides, views, blind
spots — before validation.

What went wrong in earlier cards and the card must avoid:
- **Uncredited sayings.** A borrowed line in the card without its author
  is repeated by the persona as its own (Marks). Every borrowed saying
  names its author.
- **Formulas.** A stock phrase in "Styl wypowiedzi" or "Zachowanie w
  Radzie" becomes a tic in every answer ("uczę łowić ryby" 14/36 for
  Dalio, "dwie minuty" 22/36 for Lynch, "w jaką grę grasz" 19/36 for
  Housel). Describe behaviour ("asks about the goal and horizon before
  the market"), not a sentence to say.
- **One vivid story becomes the refrain.** Removing a tic moves the
  repetition to the next vivid item (Housel's March 2020 anecdote). Map
  stories to question types and say when each fits.
- **Hagiography.** "Ślepe plamki" carries the documented criticism and
  admitted mistakes — it gives the council honest hooks.

**Gate:** the owner approves the card (v1).

## 5. Validation

1. Write `$BRAIN_PATH/knowledge/personas/<slug>/validation.json` — six
   approach dilemmas in three framings with the expected stance from the
   digests, the judge's rubric, and the tic patterns. Format and how to
   design them: [references/validation.md](references/validation.md).
2. Run `.claude/scripts/personas/validate.py <slug>` — in the background;
   it takes 36 + 36 answers and 12 judge calls. It saves after every call:
   if it stops (API limit, reboot), run the same command again.
3. **Spot-check** three or four digests against their originals: figures,
   dates, attributions. LLM digests can slip in a "generic" version of
   the person.
4. Check by hand every fabrication the judge flags — the judge
   misattributes from its own memory.
5. Write `validation.md` (method, results table persona vs bare, what
   the persona does better, weak points, limits, spot-check). Commit and
   push in brain.

Passing means: no yielding under pressure, the persona ahead of the bare
model on path and nuance, tics under control. Character is often close
to the bare model for famous people — the model already knows their
voice; that is not a failure.

**Card v2** when the run shows tics, a refrain, or a flat dilemma: fix
the card, bump `card_version`, rerun with
`validate.py <slug> --reuse-bare <previous run>` and add a "Walidacja v2"
section. Further versions only on the owner's request.

## 6. Record

1. IMPLEMENTATION.md, Step 6, the persona's item: sources and words,
   digests, card version, validation numbers (persona vs bare), gaps,
   lessons that are new. Commit on `feat/persona-<slug>`, push; the owner
   opens the PR and merges (open it with `gh` if it is logged in).
2. Update the memory file for the persona: state, commits, what is left.

## Upkeep

- New sources → new digests (same steps 2–3), then a card update if they
  change a view.
- A view that changed → mark it abandoned with its date in `era`, keep
  the old digests (supersession, never deletion).
- `card_version` goes up with every card change that would alter an
  answer; validation runs are named after it.
