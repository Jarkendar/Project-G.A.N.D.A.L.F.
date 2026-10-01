---
name: council
description: >-
  White Council — a debate of several voices on one hard question: persona
  cards (brain/knowledge/personas/, real people's approaches) and role cards
  (critic, devil's advocate), each spoken by the B.E.O.R.N. sub-agent. Runs a
  blind round, one or two critique rounds, then a synthesis of agreements,
  disagreements and their reasons — not one averaged answer. Use for a
  decision with real trade-offs (money, career, a project, a life choice),
  or when the owner says "zwołaj radę", "rada", "co by na to powiedzieli",
  "przedyskutuj to z personami", "/council".
---

# council — White Council

Several voices, one question. Each voice answers alone first, then answers
the others, and only then does the council look for common ground. The
value is in **where and why the voices disagree** — consensus is reported
only when it actually emerged.

Voices are cards; B.E.O.R.N. (`.claude/agents/beorn.md`) speaks each one.
This skill composes the council, runs the rounds and writes the synthesis.
It never speaks as a voice itself.

## 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from the project root and take `BRAIN_PATH`
(relative paths resolve from the project root). Missing or not a directory
→ tell the owner to set it / run `/init-brain`, and stop.

## 2. Frame the question

- Restate the decision in one sentence: what is being decided, between
  which options.
- If it is about the owner's own situation, gather the facts first:
  `mcp__samwise__context` for notes, G.I.M.L.I. for numbers. Voices never
  look up the owner's data themselves — whatever they should know goes
  into the question you pass them.
- If one fact would change every answer (amount, deadline, what the owner
  can afford to lose) and it is not in the request or in brain/, ask the
  owner once. Otherwise proceed and list your assumptions in the question.

## 3. Compose the council

1. Read the frontmatter of every `$BRAIN_PATH/knowledge/personas/*/persona.md`
   (`categories`, `useful_for`, `not_for`) and every
   `.claude/skills/council/roles/*.md`.
2. Pick **about three voices**, aiming for **contrast**, not a
   headcount: personas whose `useful_for` fits the question, avoiding
   those whose `not_for` rules it out; across categories when the question
   spans them.
3. Add a **role** when it earns its place: `critic` when the voices are
   likely to agree; `devils-advocate` when the owner already leans one way.
   With fewer than two fitting personas, roles fill the council — a
   council of one persona plus two roles is fine; a persona forced onto an
   off-topic question is not.
4. If the owner named voices ("z <personą> i krytykiem"), use exactly those.
5. Tell the owner the composition in one line with a reason per voice, and
   go on — do not wait for approval.

## 4. Blind round

Invoke one `beorn` sub-agent per voice, **all in one message** (parallel),
each with: `persona` or `role`, the framed `question` with the owner's
context, `round: blind`, `BRAIN_PATH`. No voice sees
another's answer.

Then read the tails (`Stanowisko`). If every voice reached the same
conclusion and no role is present, add `devils-advocate` for the critique
round — agreement reached blind is a reason to test it, not to stop.

## 5. Critique round

Again one `beorn` call per voice, in parallel, `round: critique`,
with the question and **the other voices' blind
answers in full** (without the tails). A devil's advocate added after the
blind round answers the blind round in its first turn.

**Second critique round** only when a disagreement is still live and
sharp after the first (two voices directly contradicting each other on
the point that decides the question), or when the owner asked for it. Two
critique rounds at most.

## 6. Synthesis

Written by you, in Polish, from the rounds — not a fourth opinion. Shape:

```markdown
## Rada: <question in one line>

**Skład:** <voice — why, per voice>

### Gdzie się zgadzają
<points every voice holds, with the reasoning they share>

### Gdzie się różnią — i dlaczego
<each disagreement: who holds what, and the assumption, value or
time horizon that drives the split — this is the core of the synthesis>

### Najmocniejszy argument każdego głosu
- **<voice>:** <one or two sentences>

### Konsensus
<only if it actually emerged — otherwise "Brak konsensusu." and why>

### Od czego zależy decyzja
<the one to three facts or preferences of the owner that tip it — questions,
not a verdict>

### Ostatnie słowo
- **<voice>:** <two or three sentences in that voice, from its last round>
```

Rules: attribute every claim to a voice; do not add arguments no voice
made; do not average positions into a middle one nobody held; keep the
voices' own words where they are sharp.

## 7. Save (ask first)

Show the synthesis in the conversation, then ask: "Zapisać zapis Rady
w `knowledge/councils/`? (t/n)". On yes, write
`$BRAIN_PATH/knowledge/councils/YYYY-MM-DD_<slug>.md` (slug: kebab-case,
≤40 chars, from the question), following `knowledge/councils/CLAUDE.md`:

```yaml
---
date: <YYYY-MM-DDTHH:MM:SS>
source: council
privacy: private            # always — the record holds the owner's problem
status: active
tags: [council, <category>, ...]
title: "Rada — <question in a few words>"
question: "<the framed question>"
voices: [<persona-slug>, critic, ...]
rounds: <1 or 2 critique rounds>
consensus: <yes | no | partial>
---
```

Body: the synthesis, then `## Przebieg` with `### Runda na ślepo` and
`### Krytyka` (and `### Krytyka 2`) — each voice's full answer with its
tail. Do not commit; the owner commits brain/. On no, write nothing.

## Constraints

- The record is **always** `privacy: private`, whatever the topic.
- Beorn calls carry the owner's context; it stays in this engine's context
  window (MVP exception, IMPLEMENTATION.md § "Privacy in the Claude-API
  MVP") and is never sent anywhere else.
- Adding a persona or a role means adding a card — never edit this skill
  or the agent for a new voice.
