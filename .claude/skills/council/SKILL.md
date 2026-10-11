---
name: council
description: >-
  White Council — a debate of several voices on one hard question: persona
  cards (brain/knowledge/personas/, real people's approaches) and role cards
  (critic, devil's advocate, local practitioner), each spoken by the
  B.E.O.R.N. sub-agent. Runs a blind round, one or two critique rounds, then a
  synthesis of agreements, disagreements and their reasons — not one averaged
  answer. Use for a decision with real trade-offs (money, career, a project, a
  life choice), or when the owner says "zwołaj radę", "rada", "co by na to
  powiedzieli", "przedyskutuj to z personami", "/council".
---

# council — White Council

Several voices, one question. Each voice answers alone first, then answers
the others, and only then does the council look for common ground. The
value is in **where and why the voices disagree** — consensus is reported
only when it actually emerged.

Voices are cards; B.E.O.R.N. (`.claude/agents/beorn.md`) speaks each one.
This skill composes the council and runs the rounds; E.L.R.O.N.D.
(`.claude/agents/elrond.md`) writes the synthesis and the record. It never
speaks as a voice itself.

**The debate lives in files, not in this conversation.** Every answer is
written by its voice to the Council's working folder; you see only each
voice's tail. A Council of five voices and two rounds is ~60k characters of
answers — read into the conversation, they are paid for again on every
later turn. Do not `Read` the answer files yourself.

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
- **Facts as facts, your reading as a question.** Pass what the owner said
  or what brain/ records as context; pass your own inference about it
  (a contradiction you think you see, a number you derived) as an open
  question — "sprawdź, czy …" — never as a fact. Voices build on the
  framing: in the 2026-10-05 smoke test three of four took a wrong
  orchestrator remark ("the IKE is counted twice") as given, and only the
  critic checked it.

## 3. Compose the council

1. Read the frontmatter of every `$BRAIN_PATH/knowledge/personas/*/persona.md`
   (`categories`, `useful_for`, `not_for`) and every
   `.claude/skills/council/roles/*.md`.
2. Pick **about three voices**, aiming for **contrast**, not a
   headcount: personas whose `useful_for` fits the question, avoiding
   those whose `not_for` rules it out; across categories when the question
   spans them.
3. Add a **role** when it earns its place: `critic` when the voices are
   likely to agree; `devils-advocate` when the owner already leans one way;
   `local-practitioner` when the decision runs through Polish taxes,
   accounts, instruments or law and the personas are foreign (they answer
   "outside my circle" exactly there).
   With fewer than two fitting personas, roles fill the council — a
   council of one persona plus two roles is fine; a persona forced onto an
   off-topic question is not.
4. If the owner named voices ("z <personą> i krytykiem"), use exactly those.
5. Tell the owner the composition in one line with a reason per voice, and
   go on — do not wait for approval.

## 4. The working folder

Make one folder for this Council in the session scratchpad (a temporary
directory if there is none): `<scratchpad>/council-<slug>/`, slug from the
question. **The folder must be new**: `Glob` for it first, and if it exists
— an earlier Council on the same question, a run that was broken off — take
`council-<slug>-2`, `-3`, …; never reuse it. Leftover files would be read
as this Council's answers. Write the framed question with the owner's context to
`question.md` there — once; every voice reads it from the file. Answers
will land beside it, one file per voice per round:

```
question.md
blind-<voice>.md   critique-<voice>.md   critique2-<voice>.md
synthesis.md       (Elrond's)
```

`<voice>` is the card's slug (`taleb`, `critic`, `local-practitioner`).

## 5. Blind round

Invoke one `beorn` sub-agent per voice, **all in one message** (parallel),
each with: `persona` or `role`, `round: blind`, `BRAIN_PATH`,
`input_files: [<dir>/question.md]` and
`answer_file: <dir>/blind-<voice>.md`. No voice sees another's answer.

Each voice writes its answer to the file and returns only its tail. Read
the tails (`Stanowisko`). If every voice reached the same conclusion and no
role is present, add `devils-advocate` for the critique round — agreement
reached blind is a reason to test it, not to stop.

## 6. Critique round

Again one `beorn` call per voice, in parallel, `round: critique`, with
`input_files`: `question.md` and **the other voices' blind files** (not its
own), `answer_file: <dir>/critique-<voice>.md`, and the voice's own blind
`Stanowisko` as a one-line reminder. A devil's advocate added after the
blind round answers the blind round in its first turn (it has no blind
file).

**Second critique round** only when a disagreement is still live and
sharp after the first (two voices directly contradicting each other on
the point that decides the question — judge it from the tails), or when the
owner asked for it: `input_files` are then the question and the other
voices' blind and critique files, `answer_file` is
`<dir>/critique2-<voice>.md`. Two critique rounds at most.

## 7. Synthesis and record — Elrond

Invoke the `elrond` sub-agent with `council_dir` and the `voices` (slug,
the card's name, why each was called). He reads every answer and returns
the synthesis — where the voices agree, where they differ and why, the
strongest argument of each, what the decision depends on. **Show it to the
owner in full, word for word as he returned it**, with his question whether
to save the record. Do not shorten, regroup or reword it: this text is what
goes into the record, and the owner's yes must be to the text they saw.

Send the owner's answer to the same Elrond (`SendMessage`), in the owner's
words:

- **yes** → he has the record written to
  `$BRAIN_PATH/knowledge/councils/YYYY-MM-DD_<slug>.md` — frontmatter per
  `knowledge/councils/CLAUDE.md`, the synthesis, then `## Przebieg` with
  every answer copied from the files. Pass on the path he reports.
- **a correction** ("to nie tak ujęte", "pominąłeś …") → he checks it
  against the answers and returns the corrected text, or says no voice
  held it.
- **no** → nothing is written.

Do not commit on your own; when the owner asks, committing brain/ goes
through the `ori` sub-agent, with the record's path.

If the owner wants to read a voice's whole answer before the record
exists, `Read` that one file and show it — only then.

## Constraints

- The record is **always** `privacy: private`, whatever the topic.
- Beorn calls carry the owner's context; it stays in this engine's context
  window (MVP exception, IMPLEMENTATION.md § "Privacy in the Claude-API
  MVP") and is never sent anywhere else.
- Adding a persona or a role means adding a card — never edit this skill
  or the agent for a new voice.
