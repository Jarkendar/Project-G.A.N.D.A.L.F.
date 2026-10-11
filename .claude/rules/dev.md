---
paths:
  - "*.md"
  - ".mcp.json"
  - "bin/**"
  - "data_providers/**"
  - ".claude/agents/**"
  - ".claude/hooks/**"
  - ".claude/scripts/**"
  - ".claude/rules/**"
  - ".claude/settings*.json"
  - ".claude/skills/**/SKILL.md"
---

# Developing G.A.N.D.A.L.F. — rules for work on this repo

Loaded only when a file of the repo's own code or docs is touched. The rules
every session and every agent needs (language, privacy, brain access) stay in
[CLAUDE.md](../../CLAUDE.md).

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
| G.I.M.L.I. | SQL — analytical queries over `brain/db/` (read-only MCP server) | `.claude/agents/gimli.md`, `.claude/scripts/gimli/` |
| S.A.M.W.I.S.E. | semantic search over Bilbo's index (MCP server) | `.claude/scripts/samwise/` |
| R.A.D.A.G.A.S.T. | reporting & visualization | `.claude/agents/radagast.md` |
| B.I.L.B.O. | embedding indexer (script, not reactive) | `.claude/scripts/bilbo/` |
| S.M.E.A.G.O.L. | query logger (Stop hook) | `.claude/hooks/smeagol/` |
| A.R.W.E.N. | Anki flashcards via AnkiWeb (MCP server) | `.claude/scripts/arwen/` |
| B.E.O.R.N. | speaks as a persona card (White Council voice) | `.claude/agents/beorn.md` |
| F.A.R.A.M.I.R. | calendar, reminders, delegation | planned — Step 4 |
| L.E.G.O.L.A.S. | web search — runs the forked research helpers; Gandalf route planned (Step 5) | `.claude/agents/legolas.md` |
| E.R.E.S.T.O.R. | practice briefings from brain/ records (read-only; english-prep, practice-prep) | `.claude/agents/erestor.md` |
| G.L.O.I.N. | fetches public company reports into `knowledge/finance/` | `.claude/agents/gloin.md` |
| N.A.R.V.I. | writes persona digest drafts for `/persona` (Read + Write, write-guard hook) | `.claude/agents/narvi.md` |
| T.R.E.E.B.E.A.R.D. | archivist | planned — Step 10 |

Proposed, not greenlit: G.A.L.A.D.R.I.E.L., L.I.N.D.I.R., H.A.L.D.I.R. — only
when Smeagol's logs reveal the gap.

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

## What I can and can't do in this repo

**I can:** read and search this repo; propose architecture, agents, skills,
code, tests, docs; edit files on a branch **after we've agreed on scope**;
write CC definitions in `.claude/`; update IMPLEMENTATION.md as work progresses.

**Not without explicit approval:** commit or push; edit README.md; create new
directory hierarchies or lock in library choices; install dependencies; make
outbound network calls; anything irreversible.
