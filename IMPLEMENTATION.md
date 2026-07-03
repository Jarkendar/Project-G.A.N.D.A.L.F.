# IMPLEMENTATION.md — G.A.N.D.A.L.F. execution path

**Relation to README.md:** README is the vision — *what* and *why*. This file is
the execution path — *how* and *when*. README is the canon; this file is updated
as work progresses without touching the canon.

Last updated: 2026-07-02

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
- [x] Smoke-test end-to-end: one structured query routed to Gimli, one markdown
      query answered from `brain/`. (2026-06-27: structured → Gimli returned
      active session counts from dev_tracker.db; markdown → goals.md read from
      brain/core/identity/ via grep + Read; both routes observable, privacy gate
      confirmed.)

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

### Step 2.5 — R.A.D.A.G.A.S.T.: reporting & visualization

**Goal:** give Gandalf a component that turns already-gathered data into a
readable, *analyzed* report — not just raw rows. Built ahead of the original
roadmap order (Samwise was next in sequence) at the user's request; per the
"order is a guess, one agent at a time" discipline this is exactly the kind of
reshuffle the roadmap expects.

**What it includes:**
- Radagast implemented as a CC sub-agent (`.claude/agents/radagast.md`): consumes
  data handed to it by the orchestrator (G.I.M.L.I.'s SQL results and/or `brain/`
  markdown excerpts) — it never queries a database itself, preserving Gimli's SQL
  access monopoly and the "agents do not call agents directly" rule.
- Rendering: markdown tables (default), mermaid charts (time series / breakdowns,
  validated via the Mermaid MCP tool), ASCII sparklines for compact inline trends.
- Analysis layer: trend/anomaly detection, period-over-period comparisons,
  quantified deltas — plus a mandatory **assessment** section, always distinct
  from the rendered data, in every report.
- Output: the report is **always shown in the conversation first**. Saving is
  opt-in — Radagast asks after rendering, and only writes to
  `$BRAIN_PATH/knowledge/reports/<YYYY-MM-DD>_<slug>.md` (schema in
  `.claude/brain-skeleton/knowledge/reports/CLAUDE.md`, mirroring the
  `knowledge/places/` and `knowledge/events/` pattern) on explicit confirmation.
  If declined, the report exists only in the conversation. **Revised 2026-07-01:**
  the original design (always save, then offer to open the file) was dropped after
  the open-file step proved unreliable in practice — snap-confined browsers
  couldn't see the session's scratch paths, `xdg-open` mis-routed by MIME type, and
  a stale browser tab didn't reload on re-save. Opening a file is now left to the
  user entirely; Radagast only renders and (optionally) saves.
- Wired into Gandalf's router (`.claude/skills/gandalf/SKILL.md` Step 2c): a
  report/chart/analysis-shaped request chains Step 2a/2b (fetch) → Radagast (render
  + analyze + assess + optional save).
- Documented, not-yet-built extensions: PDF export (`pandoc` + a lightweight
  HTML→PDF engine, would add a scoped `Bash` use to the PDF toolchain) and deeper
  statistics via the Wolfram MCP tools, for when the analyst role needs them.

**Tasks:**
- [x] Define Radagast sub-agent — rendering conventions, analysis rules, hard
      constraints (no SQL/DB access), render-then-optional-save flow, fixed
      response format. → `.claude/agents/radagast.md`
- [x] Add `knowledge/reports/` to the brain skeleton with its own `CLAUDE.md`.
      → `.claude/brain-skeleton/knowledge/reports/CLAUDE.md`
- [x] Wire Gandalf's router: new dispatch row + Step 2c chained orchestration.
      → `.claude/skills/gandalf/SKILL.md`
- [x] Smoke-test end-to-end: a fitness report routed Gimli → Radagast (2026-07-01,
      Strava activity trends), producing a table + trend + distinct assessment
      section, saved to `knowledge/reports/2026-07-01_fitness-trends-strava.md`
      on confirmation.
- [x] Smoke-test the mermaid path: the chart used `xychart-bar`, an invalid Mermaid
      diagram type — caught when trying to view the rendered chart locally, fixed
      to the correct `xychart-beta`. Mermaid MCP validation itself did not run
      (blocked by the sandbox classifier for PRIVATE data going to an external
      service — expected behavior, not a bug). Lesson: Radagast cannot rely on the
      MCP validator for private-data charts and must get Mermaid syntax right
      unassisted; `xychart-beta` (not `-bar`) is now called out explicitly in the
      agent's rendering conventions.

**Done when:**
- Gandalf correctly chains a report-shaped request through Gimli/brain → Radagast.
- Every Radagast report contains a distinct `## Radagast's assessment` section.
- The report always renders in the conversation; saving to `brain/knowledge/reports/`
  only happens on explicit confirmation, and is skipped cleanly on decline.
- Radagast never runs `sqlite3` or reads a database directly.

---

### Step 3 — S.A.M.W.I.S.E.: semantic retrieval over B.I.L.B.O.'s index

**Goal:** let Gandalf answer unstructured questions about `brain/` content by
querying the dense-vector index. Originally scoped as "Mode 1 grep first, Mode
2 embeddings later" — but since Bilbo (Step 9) was pulled forward and already
built a real embedding index, Samwise shipped **Mode 2 directly**. Mode 1
(grep) survives only as the explicit fallback for when the index is
unavailable, not as a transitional phase.

**What it includes:**
- `.claude/scripts/samwise/search.py` — the query-time reader. Encodes the
  query with the exact `(model, revision)` recorded in `brain/index/bilbo.db`'s
  `meta` table, cosine-ranks chunks (vectors are pre-normalized, so cosine ==
  dot product), and returns ranked paths + scores + snippets. Opens the index
  via a `mode=ro` URI connection — never a writer of `brain/index/`, that stays
  Bilbo's job exclusively. Three strategies share this one script: `semantic`
  (Samwise proper), `grep` (the keyword baseline — what Gandalf did before
  Samwise existed), and `hybrid` (Reciprocal Rank Fusion of the two) — built
  this way so the same code backs both the live agent and the comparative eval.
- `.claude/agents/samwise.md` — the sub-agent, Gimli-shaped (`Bash` + `Read`,
  no `model:` pin). Workflow: resolve `BRAIN_PATH` → run `search.py` via
  Bilbo's venv (no separate Python env — reader and writer share one set of
  embedding deps rather than installing torch twice) → fall back to direct
  grep if the index is missing/broken → `Read` the top files for real excerpts
  → return ranked results. Judges point-lookup vs. broad/enumerative questions
  and adjusts `--top-k`/`--min-score` + applies its own relevance judgment for
  the latter (see the measured limitation below).
- Gandalf routing (`.claude/skills/gandalf/SKILL.md`): unstructured queries now
  route to Samwise (Step 2d); direct grep (old Step 2b) demoted to the
  explicit fallback; Radagast (Step 2c) can chain off Gimli, Samwise, or the
  grep fallback.
- **Access model rescoped, not expanded:** Gimli's "sole SQLite reader"
  monopoly narrowed from "all of SQLite" to specifically `brain/db/` — his own
  world. Samwise (paired with Bilbo as writer) got an explicit, separate
  monopoly over `brain/index/bilbo.db` — a domain of its own. Principle: the
  system grows in **depth** (new, narrow, per-domain monopolies), not
  **breadth** (one monopoly expanding to cover more ground). Documented in
  both `gimli.md` and `samwise.md`.
- **Comparative eval** (`.claude/scripts/samwise/eval/`): `golden.jsonl` (20
  hand-labeled PL/EN queries — 15 single-file point lookups + 5 genuinely
  multi-file topical queries, approved before measuring) and `run_eval.py`
  (runs grep/semantic/hybrid in-process — one model load for the whole run —
  and reports hit@1/3/5, MRR, precision@5, recall@5, full-recall@5, a
  per-query "who picked what" table, and an F1-optimal cosine threshold swept
  over the score distribution of correct vs. incorrect semantic hits).
- Privacy: folder-level, same rule as everywhere else — `core/`/`current/` are
  PRIVATE (MVP exception: may enter the Claude API context window);
  `knowledge/` is PUBLIC. `current/smeagol/` is excluded from the index
  entirely, so Samwise never surfaces it.

**Tasks:**
- [x] Define Samwise sub-agent — query-time search, relevance ranking (via
      B.I.L.B.O.'s index), excerpt extraction. → `.claude/agents/samwise.md`
- [x] Integrate with Gandalf routing: unstructured queries go to Samwise
      (Step 2d); grep demoted to fallback. → `.claude/skills/gandalf/SKILL.md`
- [x] Test: "what do I know about X?" returns relevant excerpts from `brain/`
      with source paths and similarity scores. → smoke-tested below and via
      the golden-set eval.
- [x] Build a comparative eval: grep vs. semantic vs. hybrid, calibrate a
      similarity threshold. → `.claude/scripts/samwise/eval/`

**Smoke-test (2026-07-03):** Bilbo's index was refreshed first (6 files
changed since the 2026-07-02 build; 156 files / index current after sync).
`eval/run_eval.py` against the 20-query golden set:

| strategy | hit@1 | hit@3 | hit@5 | MRR | P@5 | R@5 | full-recall@5 |
|---|---|---|---|---|---|---|---|
| grep | 0.40 | 0.60 | 0.65 | 0.50 | 0.14 | 0.65 | 0.65 |
| **semantic** | **0.70** | 0.75 | 0.85 | **0.75** | 0.19 | 0.82 | 0.80 |
| hybrid | 0.60 | 0.75 | 0.85 | 0.70 | 0.19 | 0.82 | 0.80 |

Semantic wins outright and is the default strategy. Hybrid underperforms pure
semantic here — RRF fusion folds in enough of grep's false positives
(especially on Polish queries against English-language notes, where literal
keyword matching fails outright, e.g. `core/identity/goals.md`) to drag it
down rather than help. F1-optimal threshold: **0.5047** (precision 0.665,
recall 0.791), wired into `search.py`'s `DEFAULT_MIN_SCORE`.

**Measured limitation, not just a threshold-tuning gap:** two of the five
multi-file queries in the golden set ("what are my side-projects", "what
cycling trips have I done") scored **0/3 expected files in the top-5 across
all three strategies — even fully ungated at `--min-score 0.0`**. Per-chunk
embeddings favor literal vocabulary overlap over topical relatedness (e.g.
"projekt" is heavily overloaded by career/job documents, burying the actual
`knowledge/projects/` files for a plural, category-shaped query). No fixed
score cutoff fixes this; the mitigation lives in `samwise.md`'s workflow
(widen `--top-k`/`--min-score` for enumerative-sounding questions, then apply
judgment over the wider candidate list) rather than in the retrieval math.
Two-file multi-queries (Capgemini contract+benefits, medical/pharma tickers)
worked fine — the failure mode is specific to broad, many-document,
low-lexical-overlap categories.

**Done when:**
- Gandalf routes unstructured knowledge queries to Samwise.
- Samwise returns relevant excerpts with source paths and scores.
- Performance is acceptable on the current `brain/` size (~8ms warm per-query;
  ~6.6s cold for the one-time model load).
- A committed, reproducible eval shows semantic ≥ grep, with a calibrated
  threshold — not just an impression that it's better.

---

### Step 9 (pulled forward) — B.I.L.B.O.: embedding indexer

**Goal:** give the future Samwise reader a real dense-vector index to query
against, instead of building Samwise Mode 1 (grep) first and Mode 2
(embeddings) later as originally sequenced. Built ahead of the original order
(Samwise was next) at the user's request — the "order is a guess, Smeagol's
logs reshuffle it" discipline applies here exactly as it did for Radagast
(Step 2.5).

**What it includes:**
- Bilbo implemented as a **script**, not a conversational sub-agent —
  `.claude/scripts/bilbo/index.py`. README is explicit that Bilbo is
  *non-reactive*, scheduled, background — it doesn't fit the Gimli/Radagast/
  Samwise sub-agent pattern.
- Corpus: all markdown in `brain/`, excluding `current/smeagol/` (Smeagol's
  logs), `index/` (Bilbo's own output), and per-folder `CLAUDE.md` files
  (operating instructions, not retrievable knowledge).
- Chunking by markdown heading, sub-split to stay under ~90 words per chunk
  (the embedding model's effective window is ~128 tokens — larger chunks get
  silently truncated, not erred on).
- Embeddings via `sentence-transformers`, model
  `paraphrase-multilingual-MiniLM-L12-v2` (same model as the `prompt-vault`
  repo's `scripts/generate_embeddings.py`, for cross-project consistency) —
  **pinned to a fixed HF Hub commit revision**, not the moving `main` branch,
  so a future re-download can never silently swap in different weights. The
  `(model, revision)` pair actually used is recorded in the index's `meta`
  table; running with a different one without `--rebuild` aborts loudly
  instead of silently mixing incompatible vector spaces.
- Storage: `brain/index/bilbo.db` (SQLite, **gitignored** — derived,
  regenerable data). Deliberately outside `brain/db/`, which is G.I.M.L.I.'s
  access monopoly (`brain/db/CLAUDE.md`).
- **Incremental by construction:** a per-file content hash is compared against
  the index's manifest on every run; unchanged files are skipped entirely
  (zero embedding cost), changed files are re-chunked/re-embedded, deleted
  files have their chunks removed. This is the gap the `prompt-vault` script
  it's modeled on doesn't close (that one re-embeds everything on every run).
- Model + library versions pinned in `.claude/scripts/bilbo/requirements.txt`
  (`sentence-transformers`, `numpy` exact-pinned; `torch` left unpinned to
  avoid an unresolvable bound conflict) — the model weights themselves are
  downloaded to the local HF cache outside the repo and never committed.

**Tasks:**
- [x] Write `.claude/scripts/bilbo/index.py` — discovery, hashing, chunking,
      batched embedding, incremental SQLite upsert, `--rebuild`/`--path`/
      `--dry-run`/`--model` flags, model-consistency guard.
- [x] Pin the embedding model to a fixed HF Hub revision + record it in the
      index's `meta` table with a hard-fail on mismatch.
- [x] Pin `sentence-transformers`/`numpy` versions in `requirements.txt`.
- [x] Add `brain/index/` to `brain/.gitignore`.
- [x] Document Bilbo's scope, the Bilbo/Samwise write/read boundary, and how
      to run it in `.claude/scripts/bilbo/README.md`.
- [x] Smoke-test end-to-end on the real `brain/` (2026-07-02): first run built
      `brain/index/bilbo.db` from 153 files (17 `CLAUDE.md` files correctly
      excluded) into 1101 chunks in ~52s; a no-op re-run finished in ~0.05s
      touching 0 files (lazy-import skipped the model entirely); editing one
      file re-embedded only that file (6 chunks, ~7s); deleting a file removed
      its chunks and manifest row; a simulated revision mismatch without
      `--rebuild` aborted with exit code 1 instead of silently mixing vector
      spaces; a cosine sanity check confirmed two finance chunks score higher
      similarity (0.50) than a finance/recipe pair (0.27); confirmed the
      458 MB model cache lives in `~/.cache/huggingface` (outside both repos)
      and `git status` in both repos shows no model weights, no `.venv`, no
      `brain/index/`.

**Done when:**
- `python index.py` builds `brain/index/bilbo.db` from the real `brain/`.
- A second run with no filesystem changes re-embeds nothing.
- Editing one file re-embeds only that file's chunks; deleting a file removes
  its chunks and manifest row.
- No model weights or `.venv` are ever committed to either repo.
- A deliberate model/revision change without `--rebuild` fails loudly rather
  than corrupting the index.

**Not yet done:** no scheduler (systemd/n8n) wired up — run manually for now;
no privacy gate (documented MVP exception, same as elsewhere). The reader side
is no longer outstanding: S.A.M.W.I.S.E. (Step 3, above) now queries this
index at query time.

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
- [x] **Step 9 — B.I.L.B.O. + vector DB** — indexer over `brain/`, pulled forward
  ahead of Samwise (see detailed section above, right after Step 3). Reader
  side (Samwise, Step 3) is now built and consuming this index. Still open:
  scheduling (systemd/n8n) to run Bilbo automatically instead of manually.
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
- [ ] **E9 — Fitness DB sync (Strava → brain/db/fitness.db via /daily).**
  Schema: `activities(strava_id PK, date, sport_type, name, distance_m,
  moving_time_s, elapsed_time_s, elevation_m, average_hr, max_hr,
  average_cadence, average_speed, average_watts, calories, suffer_score,
  kilojoules, workout_type, synced_at)`. Written by `/daily` skill on every
  Strava activity match (INSERT OR REPLACE — idempotent on strava_id).
  Read exclusively through G.I.M.L.I. (access monopoly rule, documented in
  `brain/db/CLAUDE.md`). Auto-discovered by Gimli via `brain/db/*.db` glob —
  no configuration change needed. Enables: monthly/yearly distance totals,
  HR-zone trends, sport-type breakdowns, cross-period comparisons.
  Privacy: PRIVATE (same restriction as `smeagol.db`).

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
| ~~**Samwise Mode 1 → Mode 2 threshold**~~ | ~~Step 3 / Step 9~~ | **RESOLVED 2026-07-03 — moot.** Mode 2 (semantic, via Bilbo's index) shipped directly since Bilbo already existed; there was no Mode-1-first phase to graduate from. Mode 1 (grep) survives only as Samwise's fallback when the index is unavailable. |
| **Phase 2 orchestration framework** | Step 7 | LangGraph vs LlamaIndex vs custom thin wrapper. Decided when the engine abstraction layer is built. |
| **Log-analysis role** | Step 2+ | **Partially resolved 2026-07-01.** R.A.D.A.G.A.S.T. (Step 2.5) covers the *reporting/analysis* half generically (trends, anomalies, comparisons over any data handed to it) — it could analyze Smeagol's logs like any other input, once something feeds them to it. Still open: whether a dedicated FTS5 retrieval layer over Smeagol's logs (E3) is needed before that's useful, or Radagast + ad-hoc `brain/current/smeagol/` reads suffice. |
| ~~**`brain/` privacy in MVP**~~ | ~~Step 1–3~~ | **RESOLVED 2026-06-09.** Private content may enter the Claude API context window in MVP. See § "Privacy in the Claude-API MVP". Tightened in Phase 2 (Step 7). |
| **Gateway transport & channels** | E1 | Which messaging platforms to support first; how to correlate a conversation thread across channels; where session context is held between messages. |
| **Skill-authoring heuristic** | E4 | What conditions trigger "this workflow should become a skill" — what qualifies, minimum reuse threshold, and who reviews before it is promoted to `prompt-vault`. |
| **Profile self-update guardrails** | E5 | What the automated system is allowed to write or overwrite in `core/profile.md`; append-only vs field-specific rules; how proposed updates are surfaced for human review before committing. |
| **Summary-sufficiency heuristic** | E8 | Bilbo/Samwise split is settled (matches README: Bilbo non-reactive indexer, Samwise reactive retriever). Step 3 established a precedent worth reusing here: a fixed similarity threshold (0.5047, F1-calibrated) works for point-lookup queries but measurably fails broad/enumerative ones (0/3 recall on two golden-set queries even ungated) — so E8's "summary vs. fetch full file" rule should not be a bare score cutoff either. Still open: the actual decision rule (threshold + query-intent classification, most likely) and whether it needs the same point-lookup/broad-query judgment split Samwise now does. Decided when E8 is implemented. |
