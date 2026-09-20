# CLAUDE.md — G.A.N.D.A.L.F. working context

The operating manual for how we work in this repo — loaded into every session.
The vision, motivation and roadmap live in **[README.md](README.md)**; the
execution path, step status and open decisions in
**[IMPLEMENTATION.md](IMPLEMENTATION.md)**.

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

## Working agreement — git & autonomy

- I work on a **branch off `main`**, never directly on `main`.
- I show the diff before asking to commit.
- **Commit and push only after explicit approval.**
- **Conventional Commits:** `feat(<scope>): ...`, `docs: ...`, `fix: ...`.
- Every commit I author ends with exactly this trailer (no session links):
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

---

## Naming convention

All components use the `X.Y.Z.` acronym format with Tolkien references:

| Layer | Named after | Rule |
|---|---|---|
| **Agents** | Single Tolkien characters | Acronym = role; character = disposition |
| **Skills** | Tolkien events or groups | A skill is plural — *White Council*, *Last Alliance* |

If a name feels forced, the role needs rethinking — not the name. Full acronym
expansions: README.md § agents, and each agent's file in `.claude/agents/`.

| Agent | Role | Where |
|---|---|---|
| G.A.N.D.A.L.F. | orchestrator / router | `.claude/skills/gandalf/` |
| G.I.M.L.I. | SQL — analytical queries over `brain/db/` | `.claude/agents/gimli.md` |
| S.A.M.W.I.S.E. | semantic search over Bilbo's index | `.claude/agents/samwise.md` |
| R.A.D.A.G.A.S.T. | reporting & visualization | `.claude/agents/radagast.md` |
| B.I.L.B.O. | embedding indexer (script, not reactive) | `.claude/scripts/bilbo/` |
| S.M.E.A.G.O.L. | query logger (Stop hook) | `.claude/hooks/smeagol/` |
| F.A.R.A.M.I.R. | calendar, reminders, delegation | planned — Step 4 |
| L.E.G.O.L.A.S. | web search | planned — Step 5 |
| T.R.E.E.B.E.A.R.D. | archivist | planned — Step 10 |

Proposed, not greenlit: G.A.L.A.D.R.I.E.L., L.I.N.D.I.R., H.A.L.D.I.R. — only
when Smeagol's logs reveal the gap.

---

## Architecture in one breath

```
User → G.A.N.D.A.L.F. (orchestrator)
         ├─ routes to → Skill (higher-order workflow) → orchestrates Agent(s)
         ├─ routes to → Agent (single-responsibility specialist)
         └─ always logs via → S.M.E.A.G.O.L.
Engine: MVP = Claude API via Claude Code; Phase 2 = abstraction + Ollama
```

Skills orchestrate agents; agents do not call other agents directly. Multiple
orchestrators are allowed (Gandalf is the first).

---

## Ecosystem & where things live

This repo holds orchestrator and agent code only.

| Repo | Role |
|---|---|
| **G.A.N.D.A.L.F.** *(this repo)* | Orchestrator & agents. CC skills/agents/hooks/scripts in `.claude/`, launcher in `bin/`, ingestion utilities in `data_providers/`. |
| **`brain/`** *(private, sibling dir)* | The knowledge base — markdown + selective SQLite. |
| `prompt-vault` | Export destination for skills (this repo → vault, never the reverse). |
| `dev-tracker` | SQLite source for G.I.M.L.I. (via `GIMLI_EXTRA_DBS`). |
| `agentic-sdlc-forge` | External executor for dev tasks, invoked by F.A.R.A.M.I.R. |
| `pi-automate` | Homelab substrate — Docker Compose, n8n, systemd. |

Other docs: `USE-CASES.md` (owner's scenarios). `ARCHITECTURE.md` is planned
and owner-authored — not written by me.

---

## Core design principles

Every proposal must be consistent with these (full reasoning in README.md):

1. **Shape before engine** — routing, agent split and KB structure first; engines are config.
2. **Privacy is folder-level** — `brain/core/` and `current/` are private (local models only in Phase 2); `knowledge/` is public. Architectural, not a convention.
3. **Storage by question shape** — markdown by default; SQL when you'd write `GROUP BY`.
4. **Not everything deserves embeddings** — cold blobs + a thin manifest summary is often right.
5. **Append-only with supersession** — never delete; `superseded_by` replaces in default retrieval.
6. **Evolutionary schema** — easy to refactor beats comprehensive upfront design.
7. **Incremental build** — one agent at a time; Smeagol's logs reshuffle the order.

---

## What I can and can't do

**I can:** read and search this repo; propose architecture, agents, skills,
code, tests, docs; edit files on a branch **after we've agreed on scope**;
write CC definitions in `.claude/`; update IMPLEMENTATION.md as work progresses.

**Not without explicit approval:** commit or push; edit README.md; create new
directory hierarchies or lock in library choices; install dependencies; make
outbound network calls; anything irreversible.

**Never:**
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
- **How to search:** open-ended questions → S.A.M.W.I.S.E. (semantic index);
  quantitative ones → G.I.M.L.I.; exact names/keywords → `grep` + `Read`.
- Each `brain/` folder has its own `CLAUDE.md` with its rules — read it before
  writing there.
- Ideas and to-dos go to `brain/backlog/` via `/idea`, including inline requests
  ("dorzuć do backlogu", "zapisz jako pomysł").

---

## When in doubt

Ask before assuming. Reuse existing patterns. Stay true to the README canon.
