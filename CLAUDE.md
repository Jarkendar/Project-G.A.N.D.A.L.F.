# CLAUDE.md — G.A.N.D.A.L.F. working context

This file is loaded into every Claude Code session for this project. It captures
the project vision, naming conventions, design rules, and the collaboration
agreement between this codebase and me (Claude). **This is not the vision document
— [README.md](README.md) is. This file is the operating manual for how we work.**

---

## Project snapshot

**G.A.N.D.A.L.F.** is a local-first, multi-agent personal AI assistant — an
attempt at a personal J.A.R.V.I.S., running on a Raspberry Pi 5.

The system is built as a **router + specialised sub-agents** pattern, with a
**skills layer** for higher-order workflows that orchestrate multiple agents.

**Project status: concept stage. Nothing is implemented yet.**

The MVP is native to Claude Code: Gandalf as a CC skill, agents as CC sub-agents,
engine = Claude API. The local-first / Ollama goal is not abandoned — it is
*deferred*. Getting the **shape right** (skills, agents, KB, routing) comes before
getting the engine right; engines are interchangeable, architecture is not.

Full vision, motivation, architecture diagrams, and roadmap: **[README.md](README.md)**.

---

## How we communicate

- **Chat:** Polish.
- **Repo artefacts** (code, commits, documentation, PR descriptions): English —
  consistent with README.
- **Tone:** direct and factual. No excessive affirmations; no padding. If something
  is unclear, I ask rather than assume. If I disagree with a direction, I say so
  and give a reason, then follow the decision.

---

## Working agreement — git & autonomy

- I work on a **branch off `main`**. I never work directly on `main`.
- I show you the diff before asking to commit.
- **Commit and push happen only after your explicit approval.** I never commit or
  push on my own initiative.
- Commit style follows **Conventional Commits**, consistent with the repo history:
  `feat(<scope>): ...`, `docs: ...`, `fix: ...`.
- Every commit I author ends with:
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

---

## Naming convention

All components follow `X.Y.Z.` acronym format with Tolkien references. The
convention has two tiers:

| Layer | Named after | Rule |
|---|---|---|
| **Agents** | Single Tolkien characters | Acronym = role; character = disposition |
| **Skills** | Tolkien events or groups | A skill is plural — *White Council*, *Last Alliance* |

The acronym must describe the component's **role**. The character must reflect its
**disposition**. If a name feels forced, the role needs rethinking — not the name.

### Current agents (exist in design)

| Name | Acronym |
|---|---|
| **G.A.N.D.A.L.F.** (orchestrator) | *Generative Agent Navigating Databases And Local Files* |
| **S.A.M.W.I.S.E.** (semantic search) | *SQL And Markdown Wading Into Semantic Embeddings* |
| **G.I.M.L.I.** (SQL agent) | *Generative Intelligence Mining Local Information* |
| **L.E.G.O.L.A.S.** (web search) | *Local Engine Generating Outputs, Looking At Search* |
| **B.I.L.B.O.** (indexer) | *Bot Indexing Local Binary Objects* |
| **F.A.R.A.M.I.R.** (calendar & delegation) | *Forwarding Actions, Reminders And Meetings, Invoking Repositories* |
| **S.M.E.A.G.O.L.** (query logger) | *Storage Module Evaluating All Gandalf's Operational Logs* |
| **T.R.E.E.B.E.A.R.D.** (archivist) | *Temporal Repository Engine Evaluating, Archiving And Reducing Data* |

### Proposed agents (sketches, not commitments)

G.A.L.A.D.R.I.E.L. (personal advisor), L.I.N.D.I.R. (content drafting),
H.A.L.D.I.R. (outreach/lead research). These names are placeholders to show the
convention extends cleanly — none are greenlit until Smeagol's logs reveal the gap.

---

## Architecture in one breath

```
User → G.A.N.D.A.L.F. (orchestrator)
         ├─ routes to → Skill (higher-order workflow)
         │                └─ orchestrates → Agent(s)
         ├─ routes to → Agent (single-responsibility specialist)
         └─ always logs via → S.M.E.A.G.O.L.

Engine layer (under all agents):
  MVP:     Claude API via Claude Code
  Phase 2: abstraction layer + local models (Ollama) — model-portable
```

The architecture is intentionally open to multiple orchestrators (Gandalf is the
first). Skills orchestrate agents; agents do not call other agents directly.

---

## Ecosystem & where things live

This repo hosts **orchestrator and agent code** only. It is one node in a
constellation of personal projects connected by plain files, git, n8n, and HTTP.

| Repo | Role |
|---|---|
| **G.A.N.D.A.L.F.** *(this repo)* | Orchestrator & agent code. CC skill/agent definitions in `.claude/`. |
| **`brain/`** *(private repo)* | The knowledge base — markdown + selective SQLite. **I do not create or modify this repo from here.** |
| `prompt-vault` | Backup/export destination for skills. Direction: this repo → prompt-vault (new skills exported there, not sourced from there). |
| `dev-tracker` | SQLite source for G.I.M.L.I. |
| `agentic-sdlc-forge` | External executor for dev tasks, invoked by F.A.R.A.M.I.R. |
| `pi-automate` | Homelab substrate — Docker Compose, n8n flows, systemd units. |

**In this repo right now:**

```
data_providers/       # data ingestion utilities (inputs to the system)
  chats/              # browser bookmarklets for exporting AI chat transcripts
CLAUDE.md             # this file
IMPLEMENTATION.md     # executable implementation path
README.md             # canonical vision document (do not edit without being asked)
```

The on-disk layout, workspace pattern, and meta-repo topology will be covered
in a planned `ARCHITECTURE.md` — written by the project owner, not by me.

---

## Core design principles

These principles are extracted from README.md. Every proposal I make should
be consistent with them.

1. **Shape before engine.** Get the architecture right (routing, agent split, KB
   structure). Engines — Claude API, Ollama, hosted OSS — are a config change.
2. **Privacy is folder-level, not binary.** In the `brain/` repo: `core/` and
   `current/` are private (local-only models only); `knowledge/` is public. This
   split is **architectural**, not a convention to honour when convenient.
   Private folder contents never go to external APIs. *(Phase 2 target — see
   IMPLEMENTATION.md § "Privacy in the Claude-API MVP" for the current exception.)*
3. **Storage by question shape.** Markdown by default. SQL when the question is
   *how much / when / count* — i.e. when you'd write `GROUP BY`. Not the other
   way around.
4. **Not everything deserves embeddings.** Full PDFs and reference books produce
   noisy retrieval. Cold blobs + a thin manifest summary is often the right answer.
5. **Append-only with supersession.** Updates never delete. `superseded_by` pointer
   replaces the old fact in default retrieval; Treebeard can follow the chain back.
6. **Evolutionary schema.** The initial structure will be wrong in unexpected ways.
   Easy to refactor > comprehensive upfront design.
7. **Incremental build.** One agent at a time. Validate the router pattern before
   adding complexity. Smeagol's logs reshuffle the order.

---

## What I can and can't do

### I can

- Read and search any file in this repo.
- Propose architecture, agents, skills, code, tests, documentation.
- Create or edit files in this repo on a branch, **after we've agreed on scope**.
- Write Claude Code skill/sub-agent definitions in `.claude/`.
- Update `IMPLEMENTATION.md` as work progresses.

### Not without your explicit approval

- Commit or push anything.
- Edit `README.md`.
- Create new directory hierarchies or lock in library choices permanently.
- Install dependencies.
- Make outbound network calls.
- Any irreversible action.

### Never

- Curate content or manage git history in the `brain/` repo outside of sanctioned
  writes (scaffolding via `/init-brain`, ingest via skills — these are explicitly
  permitted; unilateral edits to owner-authored content are not).
- Send contents of private `brain/` folders (`core/`, `current/`) to external
  APIs. *(This is the Phase 2 target. MVP exception: the Claude-API engine may
  receive private content in its context window — consciously accepted, documented
  in IMPLEMENTATION.md § "Privacy in the Claude-API MVP".)*

---

## When in doubt

Ask before assuming. Reuse existing patterns. Stay true to the README canon. If a
proposed name feels forced, rethink the role.

---

## Companion docs

- **[IMPLEMENTATION.md](IMPLEMENTATION.md)** — the executable implementation path;
  current step, criteria for "done", open decisions. Updated as work progresses.
- **`ARCHITECTURE.md`** (planned, owner-authored) — on-disk layout, workspace
  pattern, how the ecosystem repos connect physically.
