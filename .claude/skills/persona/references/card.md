# Core card (`persona.md`)

Polish. Distilled from the digests only; every claim carries a pointer
`[…]` to its digest (year-month and short title, or the interview's
name). Size: ~400–450 lines is what the existing cards settled at — the
card is always in Beorn's context, so every line must change an answer.

## Frontmatter

```yaml
---
date: <ISO 8601>
source: persona-digest
privacy: public
status: active
tags: [persona, white-council, <category>, <themes>, <slug>]
title: "Persona — <Full Name>"
kind: persona
slug: <slug>
categories: [finanse, ...]
useful_for:
  - <question type, concrete — what the council would ask them>
not_for:
  - <question type> (lepiej <other persona>)
era:
  default: "<years and source types of the default voice>"
  abandoned: "<view → later view (year)>; ..."
card_version: 1
sources_basis: "<n> esencji (<years>): <what kinds of sources>"
---
```

## Sections, in order

1. **Header note** — "distilled from digests"; the pointer format; the
   material's gaps (what is missing and why).
2. **Zakres** — why this person (contrast with the existing personas in
   one line each), the starting thesis, the default voice and how view
   changes are used (as context; spoken about only when asked), the
   boundary of what they will not do (e.g. no transactions).
3. **Kim jest** — 3–5 sentences of biography, from the digests only;
   say what was left out on purpose.
4. **Motywacje** — what drives them, each with a pointer.
5. **Jak podejmuje decyzję** — the questions they ask, **in their
   order**; how they weigh conflicting goals; what changes their mind and
   what does not; mistakes they admit. Written as behaviour ("pyta
   konkretnie: na co są te pieniądze, kiedy…"), never as a formula to
   recite.
6. **Heurystyki decyzyjne** — numbered, each with source and year. Beorn
   cites them by number in its tail.
7. **Sposób myślenia** — the pattern distilled from the digests' *Sposób
   myślenia* sections.
8. **Poglądy** — a table: topic → stance → date range → evolution. Views
   they dropped are in the past tense.
9. **Styl wypowiedzi** — manner, register, how they address the reader.
   No stock phrases to repeat; if a saying must be listed, say when it
   fits and that it is rare.
10. **Czerwone flagi** — what makes them say no.
11. **Ślepe plamki** — documented criticism and admitted mistakes, with
    sources (including the critical reviews in the catalogue).
12. **Przykłady rozumowania** — 3–5 real decisions: situation → what they
    weighed → decision → later assessment. Note which question types
    each fits, so one story does not answer everything.
13. **Zachowanie w Radzie** — how they handle disagreement: what they
    grant, where they hold, their tone towards specific other personas
    if the digests support it.

No sample-quote section. Every borrowed saying names its author.

## Card v2 and later

Bump `card_version` and `date`/`updated`. Typical fixes after validation:
a tic rewritten as behaviour, a refrain story restricted to its question
types, a flat dilemma's topic given a reasoning example. Keep a short
note of what changed in `validation.md` ("Walidacja v2").
