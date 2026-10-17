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
---

# Developing G.A.N.D.A.L.F. — rules for work on this repo

Loaded only when a file of the repo's own code or docs is touched. The rules
every session and every agent needs (language, privacy, brain access) stay in
[CLAUDE.md](../../CLAUDE.md).

---

## Working agreement — git & autonomy

- I work on a **branch off `main`**, never directly on `main`.
- I show a plan (files and what changes in each) before writing anything.
- **Once the owner approves the plan, I branch, commit, push and open the PR
  without asking again.** Each stage of the plan is its own commit on the
  same branch.
- **I never merge** — not the PR, not into `main`. Never push to `main`,
  never force-push. Merging is the owner's.
- **Conventional Commits:** `feat(<scope>): ...`, `docs: ...`, `fix: ...`.
- Every commit I author ends with exactly this trailer (no session links):
  ```
  Co-Authored-By: Claude <noreply@anthropic.com>
  ```

A.U.L.E. (`.claude/agents/aule.md`) works on this repo from the router under
the same agreement; his hooks enforce the part about merging and pushing.

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
| G.A.N.D.A.L.F. | orchestrator / router — main-thread agent (plain `gandalf`; `--full` for a full session), write-guard hook, `pull` MCP tool for both repos | `.claude/agents/gandalf.md`, `.claude/scripts/sync/` |
| G.I.M.L.I. | SQL — analytical queries over `brain/db/` (read-only MCP server) | `.claude/agents/gimli.md`, `.claude/scripts/gimli/` |
| S.A.M.W.I.S.E. | semantic search over Bilbo's index (MCP server) | `.claude/scripts/samwise/` |
| R.A.D.A.G.A.S.T. | reporting & visualization | `.claude/agents/radagast.md` |
| B.I.L.B.O. | embedding indexer (script, not reactive) | `.claude/scripts/bilbo/` |
| S.M.E.A.G.O.L. | query logger (Stop hook) | `.claude/hooks/smeagol/` |
| A.R.W.E.N. | Anki flashcards via AnkiWeb — sub-agent that drafts and adds cards (owns the `flashcards` skill), over its MCP server | `.claude/agents/arwen.md`, `.claude/scripts/arwen/` |
| B.E.O.R.N. | speaks as a persona card (White Council voice; in a council writes its answer to a scratchpad file — write-guard hook) | `.claude/agents/beorn.md` |
| E.L.R.O.N.D. | closes a White Council — writes the synthesis from the voices' answer files and has the record assembled into `knowledge/councils/` (write-guard hook, `record` MCP tool) | `.claude/agents/elrond.md`, `.claude/scripts/elrond/` |
| F.A.R.A.M.I.R. | the calendar (Google Calendar connector) — reads the main and shared calendars, writes the main one only; deletes, edits and events with guests only on the owner's yes (consent-token hook; no brain/ access). Reminders and delegation: not built, Step 4 | `.claude/agents/faramir.md`, `.claude/hooks/faramir-guard/` |
| L.E.G.O.L.A.S. | web search — the research helpers (`research-offer`, `research-idea`, preloaded) for Balin and Círdan, or forked from a full session; a route of its own from Gandalf is planned (Step 5) | `.claude/agents/legolas.md` |
| E.R.E.S.T.O.R. | practice briefings from brain/ records (read-only; english-prep, practice-prep) — routed from Gandalf, or forked | `.claude/agents/erestor.md` |
| G.L.O.I.N. | fetches public company reports into `knowledge/finance/` — for Thorin, or forked (`fetch-finance-reports`, preloaded); no shell: EDGAR through the `edgar_reports` MCP tool, write-guard hook | `.claude/agents/gloin.md`, `.claude/scripts/thorin/` |
| N.A.R.V.I. | writes persona digest drafts for `/persona` (Read + Write, write-guard hook) | `.claude/agents/narvi.md` |
| F.R.O.D.O. | the owner's records — files into brain/ what the owner tells about their days, themselves and people (runs `daily`, `idea`, `update-core`, `add-contact`, `interview`; write-guard hook, `fitness_upsert` and `now` MCP tools, commits through Ori) | `.claude/agents/frodo.md`, `.claude/scripts/frodo/` |
| B.A.L.I.N. | career & practice records — offer dossiers, practice and English reviews (runs `analyze-offer`, `practice-review`, `english-review`; write-guard hook, research through Legolas, commits through Ori) | `.claude/agents/balin.md` |
| C.I.R.D.A.N. | project ideas — researched dossiers in `knowledge/projects/` (runs `develop-idea`; write-guard hook, research through Legolas, commits through Ori) | `.claude/agents/cirdan.md` |
| S.T.R.I.D.E.R. | packing — trip lists, post-trip reviews, the item catalogue and packing profiles (runs `pack`; write-guard hook, commits through Ori) | `.claude/agents/strider.md` |
| T.H.O.R.I.N. | the portfolio record — a myFund export into `core/finance/finance.md`, reports through Gloin, the export archived (runs `ingest-finance`, on the owner's explicit word only; write-guard hook, `read_export` and `archive_export` MCP tools, commits through Ori) | `.claude/agents/thorin.md`, `.claude/scripts/thorin/` |
| A.U.L.E. | the smith of this repo — agents, skills, routing, hooks, scripts, docs; plan first, then branch, commits and a PR, never a merge (write-guard `repo`, read guard, Bash guard) | `.claude/agents/aule.md`, `.claude/hooks/write-guard/` |
| O.R.I. | commits and pushes brain/ — the only one that may (MCP server, two tools) | `.claude/agents/ori.md`, `.claude/scripts/ori/` |
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

**Only after the plan is approved:** branch, commit, push, open a PR.

**Never:** merge, push to `main`, force-push.

**Not without explicit approval:** edit README.md; create new
directory hierarchies or lock in library choices; install dependencies; make
outbound network calls; anything irreversible.
