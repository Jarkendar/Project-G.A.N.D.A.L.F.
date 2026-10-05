# Digest (esencja) — one per source

A digest is the evidence layer: what this source shows about how the
person thinks and decides. Polish, compact (a short essay: ~150–300
words; a long memo, chapter or interview: up to ~800). The card is later
written from digests only, so anything the card will need must be here.

## Draft file

`<drafts>/<id>.md` in the scratchpad — one line of topic tags, a
separator, then the body. `assemble.py` adds the frontmatter (date,
`source: persona-digest`, privacy, tags = `persona, <slug>` + catalogue
tags + these, title, source id, type, date, URL, Wayback, sha256).

```markdown
tags: [topic-a, topic-b, topic-c]
---

# <Surname> — <Title> (<outlet or type>, <year>)

## Kontekst

When and where; what was happening (market, their life, the debate) —
only as much as the theses need. Approximate dates are marked as such.

## Kluczowe tezy

- **The thesis in bold:** what they claim and why, in your own words;
  the argument's own example or figure when it carries the point.

## Sposób myślenia

- How they get to the conclusion: analogy, history, inversion,
  probabilities, a story, arithmetic; how they act against fashion or
  under pressure; what they admit as a mistake or as not knowing; tone
  towards the reader.

## Decyzje i poglądy

- Real decisions: situation → what they weighed → decision → how they
  judged it later. Stable views stated here with their scope.

## Cytaty

> 0–2 lines, verbatim, original language — only the line that is the
> crux of the reasoning. None is fine.

## Zmiana względem wcześniejszych lat

What is new, dropped or repeated against sources already digested —
only those. "Repeats X from 2016-11" is a useful finding.
```

## Rules

- **Quotes:** the person's own words only — never a person they quote, a
  proverb, or a line from a co-written text. Check the surrounding text
  before quoting. `assemble.py` refuses a quote not found verbatim.
- **No outside knowledge.** Facts that are not in this source do not go
  into its digest, however well known.
- **Criticism of the person** (a hostile review) is digested the same
  way, but the title and *Kontekst* say plainly it is not their voice.
- **Excerpts** of a long file (book chapters, one memo of a collection)
  are digested one per excerpt; name the part in the title.
