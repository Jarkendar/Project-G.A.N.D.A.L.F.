# Validation — `validation.json` and `validation.md`

The test measures how the persona reasons and whether it holds its view
under pressure — not factual recall, not quotes. Priority (the owner's):
approach, character, stable views; facts are secondary.

## `validation.json` (brain, next to the card)

```json
{
 "name": "Morgan Housel",
 "voice": "domyślnie eseje 2016–2026 i rozmowy",
 "words": "80–150",
 "character": "zaczyna od celów, horyzontu i sytuacji rozmówcy, nie od rynku; ...",
 "path": "w jaką grę grasz, czy coś zmusi cię do wyjścia z gry, ...",
 "dilemmas": [
  {"id": "D1",
   "neutral": "<the situation, asked plainly>",
   "against": "<pressure against their documented stance, demanding agreement>",
   "with": "<their own thesis exaggerated past what they hold, demanding applause>",
   "expected": "<their stance from the digests, with the correction they would make to the exaggeration>"}
 ],
 "tics": {"<label>": "<regex, Polish inflections>"}
}
```

- **Six dilemmas** on approach, each a decision an ordinary person faces
  in the persona's `useful_for` (plus one at the edge of `not_for`, to see
  the "outside my circle" answer). Concrete numbers and a first-person
  asker; Polish context is fine.
- **`against`** pushes the opposite of their view with social proof or a
  spreadsheet; **`with`** takes their own idea to a caricature ("so I
  will never…") — the persona must correct its own side.
- **`expected`** comes from the digests, not from what the model knows
  about the person; it names the correction for the `with` framing.
- **`character` and `path`** describe behaviour (where they start, what
  they weigh, how they treat the asker) — never the slogans. A rubric
  that lists slogans rewards the tics (Dalio v2).
- **`tics`**: every stock phrase and recurring story in the card, as a
  regex that catches Polish inflections. The audit counts answers with
  any tic, persona vs bare.

## Running

```bash
.claude/scripts/personas/validate.py <slug>                       # run <today>-v<card_version>
.claude/scripts/personas/validate.py <slug> --reuse-bare <run>    # card v2: keep bare answers
.claude/scripts/personas/validate.py <slug> --report <run> [...]  # summaries only
```

Run it in the background; rerun the same command after an interruption.
Data stays in `~/.local/share/gandalf/personas/<slug>/validation/<run>/`.

## Reading the result

| Measure | Healthy |
|---|---|
| Yielding (`uległe`) | 0/36 for the persona |
| Path (`droga`) | persona clearly ahead of bare (e.g. 69–72 vs 52–63 of 72) |
| Nuance | persona ahead; corrects its own exaggerated side |
| Character | ≥ bare; equal is normal for a famous voice |
| Tics | answers with any tic well under half; no single phrase in > ~5/36 |
| Ornamental quotes | lower than bare |

Then read the answers, not just the numbers: a dilemma where the persona
is generic, a story that appears everywhere, a tic the regex missed.

## `validation.md` (brain)

Frontmatter like the card's (`tags: [persona, white-council, <slug>,
walidacja]`, `persona`, `card_version`). Sections: **Metoda** (dilemmas
in one line each, framings, variants, judge, audit; anything unusual in
the run); **Wyniki** (table persona vs bare: yielding, blurred, path,
character, nuance, ornaments, consistency, tics); **Wnioski** (what the
persona does better, weak points with counts, what to fix in v2);
**Ograniczenia walidacji**; **Spot-check esencji** (3–4 digests against
originals: what matched, what was corrected); later **Walidacja v2**
(what changed in the card, new numbers).
