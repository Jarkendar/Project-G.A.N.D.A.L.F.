# IMPLEMENTATION.md — G.A.N.D.A.L.F. execution path

**Relation to README.md:** README is the vision — *what* and *why*. This file is
the execution path — *how* and *when*. README is the canon; this file is updated
as work progresses without touching the canon.

Last updated: 2026-06-26

---

## Privacy in the Claude-API MVP

**Decision (2026-06-09):** Private `brain/` content (`core/`, `current/`) **may
enter the Claude API context window** in the MVP. This is a conscious, time-boxed
exception. Reasons:

- The MVP engine *is* the Claude API. Building a local redaction layer before the
  router pattern is validated would optimise prematurely.
- The user controls what enters the context by deciding which `brain/` files to
  read and what queries to ask.
- All content stays in this user's Claude account — it is not shared with others.

**Phase 2 obligation:** when the engine abstraction layer and local models (Ollama)
are introduced (Step 7), this exception is closed. Private folders route to
local-only models; the API context window never sees their content.

**Not affected:** the *architecture* of the privacy split (folder-level, enforced
per `CLAUDE.md` in each folder) is set now, even though enforcement is relaxed for
the MVP. This means Phase 2 tightening is a config/routing change, not a redesign.

**Strava MCP (2026-06-22):** the project's first concrete MCP wiring. Uses the
self-hosted `@r-huijts/strava-mcp-server` (the official hosted connector at
`mcp.strava.com` requires a Strava subscription, which the user does not have).
Activity/HR/GPS data returned by this server enters the Claude API context window
under the same MVP exception above. Credentials (`STRAVA_CLIENT_ID`/`SECRET`) live
only in gitignored `.claude/gandalf.env`; OAuth access/refresh tokens are managed by
the server itself in `~/.config/strava-mcp/config.json`, outside this repo. The
backlog's GPS→aggregate filtering (`brain/backlog/projects/mcp-strava-agent.md`) is
deferred — meaningful once Phase 2 (Step 7, local-first) is reached, or sooner if a
custom wrapper/fork is built. Revisit this server choice if a Strava subscription
is ever acquired (the official connector then removes credential management
entirely — see backlog note).

---

## Guiding rules

- **Shape before engine.** MVP runs on Claude Code (Gandalf as a skill, agents as
  sub-agents, engine = Claude API). Local-first / Ollama is Phase 2 — consciously
  deferred. Architecture is not interchangeable; engines are.
- **One agent at a time.** Validate the router pattern before adding complexity.
  The order below is a guess; Smeagol's logs will reshuffle it.
- **Stack stays tentative** beyond the MVP runtime choice. Library decisions
  (LangGraph vs LlamaIndex, ChromaDB vs alternatives) are made per step, not
  upfront.
- **Privacy enforced from day one — Phase 2 target.** The goal is that private
  `brain/` folders (`core/`, `current/`) never reach external APIs; enforced by code
  in Phase 2. **MVP exception:** in the Claude-API MVP the engine may receive private
  content in its context window — consciously accepted (see § "Privacy in the
  Claude-API MVP" below) with the intent to tighten in Phase 2.
- **CC artefacts live here.** Claude Code skill and sub-agent definitions belong
  in `.claude/` in this repo. New skills are *exported* to `prompt-vault` as
  backup — that is the direction (this repo → vault), not the reverse.

---

## Near-term (detailed)

### Step 0 — brain/ scaffold + Gandalf configuration

**Goal:** establish the `brain/` knowledge repository and wire it to Gandalf
before any agent reads or writes data. Nothing else can be validated without this.

**What it includes:**
- `brain/` repo initialized with full folder structure and per-folder `CLAUDE.md` files.
- `_meta/schema.md`, `_meta/queue.jsonl`, `_meta/manifest.json` in place.
- `.claude/gandalf.env` configured with a valid `BRAIN_PATH`.
- `init-brain` skill tested end-to-end (creation mode and validation mode).

**Tasks:**
- [x] Copy `.claude/gandalf.env.example` → `.claude/gandalf.env`, set `BRAIN_PATH`.
- [x] Run `/init-brain` — verify scaffold is created correctly at the configured path.
- [x] Confirm each folder's `CLAUDE.md` is present and readable.
- [x] Living document model for `core/` established: seven template files in
  `core/identity/`, `core/health/`, `core/finance/` (profile, goals, contacts,
  health, body, fitness, finance); `core/CLAUDE.md` updated.
  `/update-core` skill added for curated writes with privacy gate and user confirmation.
  All templates extracted to `.claude/brain-skeleton/` (single source of truth);
  `/init-brain` copies the skeleton tree on creation and validates against it.
- [x] Seed `core/identity/profile.md`, `goals.md`, `contacts.md` with real data
  (run `/update-core` interactively or fill manually).
- [x] `/daily` skill added — general (non-dev) daily-note dispatcher. Parses a
  free-form note, routes each item to the skill/convention that already owns
  its target (`/update-core`, `/add-contact`, `/idea`), and keeps an
  append-only journal under `current/daily/` (monthly digest + yearly index —
  no per-day files, idempotent re-runs merge rather than duplicate). Folder
  template added to `.claude/brain-skeleton/current/daily/`.
- [x] (Optional for MVP) Install pre-commit hook in `brain/` for frontmatter validation.
  Validator lives in `.claude/hooks/brain/pre-commit` (kept out of the data-only
  `brain/` repo); `/init-brain` Step 5 points `brain/`'s `core.hooksPath` at it.

**Done when:**
- `brain/` exists at the configured path with correct folder structure.
- Each folder has its own `CLAUDE.md` with correct privacy rules.
- `_meta/schema.md` is in place and matches the spec.
- Gandalf can resolve `BRAIN_PATH` at startup without error.

---

### Step 1 — MVP: Gandalf + G.I.M.L.I. + `brain/` markdown

**Goal:** validate the router pattern and the shape of the `brain/` repo before
adding any further agents. No embeddings, no Ollama, no Pi.

**What it includes:**
- Gandalf implemented as a Claude Code skill (`.claude/skills/gandalf/SKILL.md`).
- G.I.M.L.I. implemented as a CC sub-agent (`.claude/agents/gimli.md`): schema-aware
  SQL queries against a SQLite database registry (`brain/db/*.db` ∪ `GIMLI_EXTRA_DBS`).
  GIMLI is source-agnostic — dev-tracker is one entry in the registry, not special-cased.
- Direct markdown read access to `brain/` for unstructured queries (no vector DB —
  Gandalf reads files directly via grep + Read; Samwise is Step 3).

**Tasks:**
- [x] Define Gandalf skill in `.claude/` — routing logic, privacy gate, synthesis.
      → `.claude/skills/gandalf/SKILL.md`
- [x] Define G.I.M.L.I. sub-agent — schema discovery, query generation, result
      formatting, read-only enforcement. → `.claude/agents/gimli.md`
- [x] Connect to a SQLite database registry: `brain/db/*.db` ∪ `GIMLI_EXTRA_DBS`
      (real `dev_tracker.db` from `dev_activity_deamon` as the smoke-test fixture).
      Configured in `.claude/gandalf.env`.
- [ ] Smoke-test end-to-end: one structured query routed to Gimli, one markdown
      query answered from `brain/`.

**Done when:**
- Gandalf correctly routes a `how much / when / count` question to Gimli.
- Gandalf correctly reads a relevant markdown file from `brain/` for an
  unstructured question.
- No private `brain/` folder contents are passed to the Claude API beyond the
  MVP exception window.
- The router pattern is observable (even if only via stdout logging for now).

---

### Step 2 — S.M.E.A.G.O.L.: query logging

**Goal:** instrument every Gandalf interaction from day one, before there is
anything to analyse. Smeagol's logs are the feedback loop that will reshuffle
this roadmap.

**What it includes:**
- Smeagol implemented as a lightweight Claude Code `Stop` hook
  (`.claude/hooks/smeagol/log-turn.py`) rather than a sub-agent — fires once per
  turn, reads only that turn's transcript slice, writes a structured log entry:
  timestamp, route taken, agents called, latency, outcome flag.
- Log destination: JSONL, one file per day, in `brain/current/smeagol/`. Schema
  fixed by `brain/current/smeagol/CLAUDE.md`.
- Smeagol **writes only**. Analysis is a separate, future role.

**Tasks:**
- [x] Decide log format (JSONL vs append-only MD vs SQLite) and destination —
  JSONL in `brain/current/smeagol/YYYY-MM-DD.jsonl`.
- [x] Implement Smeagol as a side-effect of every turn — Stop hook, not gated on
  the (not-yet-built) Gandalf skill, so logging started ahead of Step 1.
- [x] Verify: every turn produces a log entry (confirmed via real
  `brain/current/smeagol/*.jsonl` output).

**Done when:**
- Every turn produces a parseable log entry (route, agents, latency, outcome). ✅
- Logs accumulate without blocking the main response path. ✅ (hook swallows
  all exceptions, never fails the user's turn)

---

### Step 3 — S.A.M.W.I.S.E. (minimal): markdown retrieval

**Goal:** let Gandalf answer unstructured questions about `brain/` content
without a vector DB. Add embeddings only when direct retrieval proves insufficient.

**What it includes:**
- Samwise sub-agent with a two-mode design:
  1. **Mode 1 (current):** grep / filename search + LLM-read of matching files.
     No embedding infrastructure needed.
  2. **Mode 2 (future):** ChromaDB index over `brain/` markdown files — layered on
     top, markdown stays canonical. Activated when Mode 1 starts feeling slow or
     noisy.
- Privacy boundary: `core/` and `current/` folders accessible only to
  local-model reads (Phase 2); in MVP, Gandalf reads them directly without
  sending content to the API beyond what the user query requires.

**Tasks:**
- [ ] Define Samwise sub-agent — file search, relevance scoring, excerpt extraction.
- [ ] Integrate with Gandalf routing: semantic / unstructured queries go to Samwise.
- [ ] Test: "what do I know about X?" returns relevant excerpts from `brain/`.

**Done when:**
- Gandalf routes unstructured knowledge queries to Samwise.
- Samwise returns relevant excerpts with source paths.
- Performance is acceptable on the current `brain/` size (Mode 1).

---

## Long-term (condensed)

Steps 4–11 from the README roadmap, condensed for orientation. Detailed tasks will
be written here as each step becomes near-term. **Order is a guess; Smeagol's logs
reshuffle it.**

- [ ] **Step 4 — F.A.R.A.M.I.R.** — calendar integration, reminders, delegation
  to `agentic-sdlc-forge` for dev tasks via n8n / HTTP.
- [ ] **Step 5 — L.E.G.O.L.A.S.** — outbound web search (DuckDuckGo first,
  self-hosted SearXNG later). Only agent with external network access.
- [ ] **Step 6 — First skill: White Council** — multi-perspective deliberation
  over a hard question; validates the agent/skill split in practice.
- [ ] **Step 7 — Ollama + engine abstraction** — model-agnostic interface; agents
  become portable across Claude API, local Ollama, and hosted OSS. This is the
  point at which the system actually becomes local-first.
- [ ] **Step 8 — Migrate to RPi 5** — observe what breaks under ARM + memory
  constraints, optimise model choices.
- [ ] **Step 9 — B.I.L.B.O. + vector DB** — scheduled indexer over `brain/`;
  ChromaDB layer over markdown files; Samwise switches to Mode 2. Activated once
  the brain repo grows past the "grep is fine" threshold.
- [ ] **Step 10 — T.R.E.E.B.E.A.R.D.** — nightly compression pass, supersession
  resolution, archive retrieval. Meaningful once 6–12 months of data accumulate.
- [ ] **Step 11 — Optional voice layer** — Whisper.cpp (STT) + Piper TTS —
  only if real usage proves it's wanted.

---

## Capability extensions (beyond the current roadmap)

These capabilities complement steps 1–11 without replacing them. They are
sequenced separately because they cut across multiple steps or depend on
capabilities that do not exist yet. Detailed tasks will be written when the
relevant prerequisites are in place. **Order is still a guess — Smeagol's logs
reshuffle it.**

- [ ] **E1 — Conversational gateway (multi-channel + voice in).** Two-way
  interface: hold a conversation with Gandalf via Telegram, Signal, email, or
  voice — one conversation thread that follows you across channels. Builds on the
  existing n8n ingestion layer by adding a response path. Gateway dispatch is a
  natural fit for a new agent (posłaniec/dispatcher role). Prerequisites: Step 2
  (Smeagol, for per-session correlation) and a deployed n8n flow in `pi-automate`.
- [ ] **E2 — Proactive scheduler (extends F.A.R.A.M.I.R.).** Natural-language
  recurring tasks initiated by the system rather than the user — morning briefings,
  weekly retros, bill-due reminders — delivered through the gateway (E1). Shifts
  the system from purely reactive Q&A to an assistant that shows up unprompted.
  Substrate: systemd timers and n8n already in `pi-automate`; scheduling logic
  extends Step 4 (Faramir).
- [ ] **E3 — Session and log retrieval (FTS5).** Concrete implementation for the
  unassigned "log-analysis" role in the step table: SQLite FTS5 index over
  Smeagol's logs and `brain/conversations/` enables natural-language queries over
  past sessions (*"what did we discuss about X?"*, *"when did I last work on Y?"*).
  Tightly coupled to Steps 2 and 3; inexpensive to add once the log format is
  stable.
- [ ] **E4 — Self-improving skills loop.** After a successful multi-agent workflow,
  a reflection step asks whether the sequence generalises; if yes, it writes a
  reusable skill file and exports it to `prompt-vault`. The fellowship's playbook
  grows with use rather than requiring manual authoring. Requires a triggering
  heuristic and a human-review gate to prevent skill noise. Logically dependent on
  Step 6 (White Council validates the pattern first).
- [ ] **E5 — Evolving user profile.** Manual foundation in place (2026-06-10):
  living documents in `core/identity/` (`profile.md`, `goals.md`, `contacts.md`),
  `/update-core` skill for curated human-confirmed writes. Next: agent-curated
  updates (G.A.L.A.D.R.I.E.L.'s model), append-only with `superseded_by` pointers.
  Profile data stays in private `core/`; auto-update logic must not bypass the
  privacy gate. See parking lot: "Profile self-update guardrails".
- [ ] **E6 — Programmatic tool calling (RPC).** Phase 2+ addition under the engine
  abstraction layer (Step 7): the agent writes a short script that calls tools
  procedurally, collapsing multi-step pipelines into a single inference turn.
  Reduces per-query token cost on a Pi budget. Requires an execution sandbox. Not
  meaningful before the engine abstraction exists.
- [ ] **E7 — Finance layer (3 skills).** Structure in place (2026-06-12):
  `core/finance/finance.md` (positions, accounts, strategy) +
  `knowledge/finance/<TICKER>/` (dated report files) +
  `knowledge/finance/analyses/` (pre-decision deliberations).
  Three skills to build when the structure is populated:
  1. **Report ingestion** — processes automated report summary from `current/inbox/`
     → appends to `knowledge/finance/<TICKER>/YYYY-QQ.md` (or annual).
  2. **Pre-investment analysis** — guided deliberation before a new position;
     writes to `knowledge/finance/analyses/YYYY-MM-DD_<TICKER>_pre-investment.md`.
  3. **Portfolio report** — periodic snapshot across all positions in `finance.md`
     cross-referenced with latest reports; output to `analyses/` or `conversations/`.
  Prerequisites: `finance.md` populated (personal data session), at least one
  company folder with a report.
- [ ] **E8 — Cold storage offload (Google Drive) for `knowledge/` binaries.**
  Large binary files in `knowledge/` (PDFs, reference docs — never `core/`/`current/`,
  which stay local per the privacy split) move to Google Drive; a DB row holds the
  link, with a short summary/manifest kept in `brain/` as the always-available
  fallback. Indexing splits along the existing Bilbo/Samwise boundary: **Bilbo**
  (background, non-reactive — see README) builds and maintains two index tiers —
  a lightweight pointer/manifest index over the full files and a full embedding
  index over the summaries; **Samwise** (reactive, query-time) compares the
  incoming query against both tiers and decides whether the summary answers it or
  whether to resolve the stored link and fetch the full file on demand. Keeps cold
  blobs off the Pi's disk without losing them to opaque storage. Prerequisites:
  Step 3 (Samwise Mode 1 — extend to query both tiers) and Step 9 (Bilbo + vector
  DB — extend the write path to populate both tiers and store Drive links).

---

## Open decisions / parking lot

These points need a decision before or during the relevant step. Documented here
so they don't get lost.

| Decision | Relevant at | Options / notes |
|---|---|---|
| ~~**SQLite for MVP**~~ | ~~Step 1~~ | **RESOLVED 2026-06-26.** Real `dev_tracker.db` from `dev_activity_deamon` repo as smoke-test fixture; GIMLI is source-agnostic (registry: `brain/db/*.db` ∪ `GIMLI_EXTRA_DBS`). Postgres deferred to Phase 2 / Step 8. |
| ~~**Smeagol log destination**~~ | ~~Step 2~~ | **RESOLVED 2026-06-24.** JSONL, one file per day, in `brain/current/smeagol/`, written by a Stop hook. See Step 2 above. |
| **Samwise Mode 1 → Mode 2 threshold** | Step 3 / Step 9 | No hard number yet. Signal: Smeagol logs show slow or irrelevant retrieval. |
| **Phase 2 orchestration framework** | Step 7 | LangGraph vs LlamaIndex vs custom thin wrapper. Decided when the engine abstraction layer is built. |
| **Log-analysis role** | Step 2+ | Reads Smeagol's logs, surfaces gaps and patterns. Agent or skill? Tolkien persona? Deliberately unassigned until the logs exist. |
| ~~**`brain/` privacy in MVP**~~ | ~~Step 1–3~~ | **RESOLVED 2026-06-09.** Private content may enter the Claude API context window in MVP. See § "Privacy in the Claude-API MVP". Tightened in Phase 2 (Step 7). |
| **Gateway transport & channels** | E1 | Which messaging platforms to support first; how to correlate a conversation thread across channels; where session context is held between messages. |
| **Skill-authoring heuristic** | E4 | What conditions trigger "this workflow should become a skill" — what qualifies, minimum reuse threshold, and who reviews before it is promoted to `prompt-vault`. |
| **Profile self-update guardrails** | E5 | What the automated system is allowed to write or overwrite in `core/profile.md`; append-only vs field-specific rules; how proposed updates are surfaced for human review before committing. |
| **Summary-sufficiency heuristic** | E8 | Bilbo/Samwise split is settled (matches README: Bilbo non-reactive indexer, Samwise reactive retriever). Still open: the actual rule Samwise uses to decide "summary is enough" vs "fetch full file from Drive" — similarity-score threshold, query-intent classification, or something else. Decided when Step 9 is implemented. |
