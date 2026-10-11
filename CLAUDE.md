# CLAUDE.md — G.A.N.D.A.L.F. working context

What every session and every agent needs — loaded each time, so kept short.
Rules for developing this repo (git, naming, the agent table, ecosystem,
design principles) are in **[.claude/rules/dev.md](.claude/rules/dev.md)** and
load when its files are touched. Vision and roadmap: **[README.md](README.md)**;
execution path and status: **[IMPLEMENTATION.md](IMPLEMENTATION.md)**.

---

## Project snapshot

**G.A.N.D.A.L.F.** is a local-first, multi-agent personal AI assistant (a
personal J.A.R.V.I.S.) on a Raspberry Pi 5: a **router + specialised
sub-agents**, with **skills** for higher-order workflows.

**Status: MVP running on Claude Code** — Gandalf as a CC skill, agents as CC
sub-agents, engine = Claude API. Local-first (Ollama) is *deferred*, not
abandoned: shape first, engine later. For what is built and what is next, read
IMPLEMENTATION.md — don't infer it from this file.

---

## How we communicate

- **Chat:** Polish.
- **Repo artefacts** (code, commits, docs, PR descriptions): English.
- **Tone:** direct and factual, no padding. If something is unclear, I ask. If I
  disagree, I say so with a reason, then follow the decision.

---

## Architecture in one breath

```
User ↔ G.A.N.D.A.L.F. (router — holds the conversation, asks, confirms)
         ├─ routes to → domain agent (owns its domain's skills)
         │                 └─ task agents (its own sub-team, one level deep)
         ├─ routes to → single-task agent (gimli, radagast, beorn, …)
         └─ always logs via → S.M.E.A.G.O.L.
Engine: MVP = Claude API via Claude Code; Phase 2 = abstraction + Ollama
```

The target shape; it is being built one domain at a time — IMPLEMENTATION.md
§ "Least privilege & token diet", Stage 3. A sub-agent cannot ask the owner:
it returns questions or a draft, the router asks and sends the answer back.
Privacy is folder-level: `brain/core/` and `current/` are private,
`knowledge/` is public. Multiple orchestrators are allowed (Gandalf is the
first).

---

## Never

- Curate content or manage git history in `brain/` outside sanctioned writes
  (`/init-brain` scaffolding, skill ingest) — no unilateral edits to
  owner-authored content.
- Send private `brain/` content (`core/`, `current/`) to external APIs.
  *MVP exception: the Claude-API engine itself may see it — IMPLEMENTATION.md
  § "Privacy in the Claude-API MVP".*

---

## Brain access

- Read `.claude/gandalf.env` to resolve `BRAIN_PATH` (usually `../brain`) and
  `GIMLI_EXTRA_DBS` (extra SQLite sources for Gimli). If `BRAIN_PATH` is
  missing, note it once and continue without brain access.
- Treat `brain/` as a knowledge source in **any** conversation, not only in
  skills — search it proactively when the question touches personal data.
- **How to search:** open-ended questions → S.A.M.W.I.S.E. (`mcp__samwise__context`);
  quantitative ones → G.I.M.L.I.; exact names/keywords → `rg` (ripgrep) + `Read`.
- Each `brain/` folder has its own `CLAUDE.md` with its rules — read it before
  writing there.
- Ideas and to-dos go to `brain/backlog/` via `/idea`, including inline requests
  ("dorzuć do backlogu", "zapisz jako pomysł").

---

## When in doubt

Ask before assuming. Reuse existing patterns. Stay true to the README canon.
Before changing anything in this repo, read `.claude/rules/dev.md`.
