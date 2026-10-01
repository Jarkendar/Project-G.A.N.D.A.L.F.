# CLAUDE.md — knowledge/councils/

Records of White Council debates written by the `/council` skill: the
owner's question, the voices, every round and the synthesis. One debate =
one file. `/council` is the sole writer, and only after the owner confirms.

## Privacy

**Every file here is `privacy: private`** — a record always contains the
owner's problem and context. This overrides the `knowledge/` default
(public); a file here without `privacy: private` is a bug.

## File naming

`YYYY-MM-DD_<slug>.md` — slug in kebab-case, ≤40 chars, from the question.

## Frontmatter

```yaml
date: <YYYY-MM-DDTHH:MM:SS>
source: council
privacy: private
status: active
tags: [council, <category>, ...]
title: "Rada — <question in a few words>"
question: "<the framed question>"
voices: [buffett, critic]      # persona and role slugs
rounds: 1                      # critique rounds after the blind round
consensus: no                  # yes | no | partial
```

## Body

The synthesis (agreements, disagreements and why, strongest argument per
voice, consensus, what the decision depends on, last word per voice),
then `## Przebieg` with every round in full.

## Not allowed

Editing a record after the fact — a new debate on the same question is a
new file (`supersedes:` if it replaces the old one).
