# IMPLEMENTATION.md — G.A.N.D.A.L.F. execution path

**Relation to README.md:** README is the vision — *what* and *why*. This file is
the execution path — *how* and *when*. README is the canon; this file is updated
as work progresses without touching the canon.

Last updated: 2026-09-22

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
  *(2026-09-18: rule files — every `CLAUDE.md` and `_meta/schema.md` — are
  authored in brain/ and reach sessions through a hook; the skeleton keeps
  generic bootstrap copies used only when creating a new brain/. See parking
  lot: "brain/ rules — single source" and "scaffolding a new brain/".)*
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
- **Comparative eval** (`.claude/scripts/samwise/eval/`): a golden set of 20
  hand-labeled PL/EN queries — 15 single-file point lookups + 5 genuinely
  multi-file topical queries, approved before measuring (since 2026-09-22
  kept privately in `brain/_meta/eval/`) — and `run_eval.py`
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
multi-file queries in the golden set — both broad, category-shaped ones
expecting three documents each — scored **0/3 expected files in the top-5
across all three strategies, even fully ungated at `--min-score 0.0`**.
Per-chunk embeddings favor literal vocabulary overlap over topical
relatedness: a category noun that recurs across unrelated documents buries
the handful of files that actually belong to that category. No fixed score
cutoff fixes this; the mitigation lives in `samwise.md`'s workflow (widen
`--top-k`/`--min-score` for enumerative-sounding questions, then apply
judgment over the wider candidate list) rather than in the retrieval math.
The two-file multi-queries worked fine — the failure mode is specific to
broad, many-document, low-lexical-overlap categories.

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

**Not yet done:** no privacy gate (documented MVP exception, same as
elsewhere). The scheduler and the reader side are no longer outstanding:
brain/'s `post-commit`/`post-merge` hooks reindex automatically (see the
parking lot), and S.A.M.W.I.S.E. (Step 3, above) queries this index at query
time.

**Pi bootstrap + measurement pass (2026-09-22).** Until now Bilbo had only
ever run on the old workstation; the Pi had no venv, no model cache and no
`brain/index/bilbo.db`. First run on the Pi, and the first measurements taken
against the real `brain/` at its current size:

| | |
|---|---|
| Index | 262 files → 1756 chunks, `bilbo.db` 4.7 MB (gitignored in brain/) |
| Full build | 180 s (132 s of it in `model.encode`) |
| No-op re-run | 0.0 s — 262 files skipped, model never loaded |
| Model cache | 458 MB in `~/.cache/huggingface` |

- **torch resolves to the CUDA build on aarch64.** `pip install -r
  requirements.txt` pulled `torch==2.14.0+cu130` plus ~4 GB of `nvidia-*`
  packages: PyPI's ARM wheels now target ARM server GPUs. Replaced with the
  CPU wheel from PyTorch's own index (5.6 GB → 1.3 GB venv). Documented in
  `.claude/scripts/bilbo/README.md`; not pinnable in `requirements.txt`,
  since the wheel lives on a separate index.
- **41% of chunks are silently truncated.** `MAX_CHUNK_WORDS = 90` bounds
  *words*, but the model's window is 128 *tokens*: 713/1756 chunks exceed it
  and ~19% of all tokens (40 k of 206 k) never reach the encoder. Token
  lengths: p50 112, p90 208, max 350. Table-heavy sections are the worst
  offenders — a 49-word chunk of one table tokenized to 323. This is the
  headline input to chunking v2.
- **The eval was measuring against a set that no longer matched the corpus.**
  Re-running `eval/run_eval.py` first gave semantic hit@1 0.45 / MRR 0.48
  (grep 0.20 / 0.27, hybrid 0.40 / 0.47) — far below the 0.70 / 0.75 recorded
  on 2026-07-03. Cause was the eval set, not retrieval: the in-repo copy had
  been rewritten to keep personal content out of a public repo, and **6 of
  its 20 queries expected targets that no longer resolved**, unhittable by
  construction (≈0.64 hit@1 over the 14 still-valid ones). Fixed the same day
  by moving the golden set out of this repo entirely — see the parking lot
  entry, and § Step 3 for where it now lives. **Re-measured against the
  restored set: semantic hit@1 0.70 / MRR 0.73 (grep 0.25 / 0.35, hybrid 0.55
  / 0.66)** — level with 2026-07-03 despite the corpus growing from 153 to
  262 files, so nothing regressed in retrieval itself. One drift worth noting:
  the F1-optimal threshold is now **0.5454** against the 0.5047 hard-coded in
  `search.py` (`DEFAULT_MIN_SCORE`) — not yet changed, since a threshold bump
  narrows what Samwise returns and belongs with chunking v2's recalibration.

**Index v2 — planned (2026-09-24).** "Chunking v2" grew into a redesign of
the whole index after the owner set the requirements and a round of research.
Planned only; no phase has started.

*Requirements (owner):* no word limits and no rigid embedding window;
logically coherent chunks; **hierarchical chunking** with rich per-chunk
metadata stored next to the vector; at query time the best (smallest) hit is
**expanded** a level up and to the most relevant linked neighbours; PL + EN;
fits a Raspberry Pi 5 with 8 GB; reranker included; the engine must later
move to its own repo and serve other projects.

*What the research changed:*
- **The model is the bigger bottleneck than chunking.** On PL-MTEB the current
  `paraphrase-multilingual-MiniLM-L12-v2` scores **30.4** on Polish retrieval
  — the lowest of all models listed (multilingual-e5-small 46.0,
  snowflake-arctic-embed-m-v2.0 52.2, Qwen3-Embedding-0.6B 48.6) — on top of
  its 128-token window. Pi-sized candidates with long windows:
  `granite-embedding-97m-multilingual-r2` (97M, 32K, Polish explicitly
  trained, not in PL-MTEB), `granite-embedding-311m-multilingual-r2` (311M,
  32K, Matryoshka), `snowflake-arctic-embed-m-v2.0` (305M, 8K, Matryoshka),
  `multilingual-e5-small` (118M, 512). A long window turns chunk size into a
  structural choice instead of a model limit.
- **Segmentation stays heuristic.** Semantic/LLM-driven splitting does not
  reliably beat structure-based splitting and costs far more (Qu et al.,
  NAACL 2025 Findings), and brain/ is markdown whose headings already mark
  the boundaries. The LLM is used for **enrichment** instead: summaries,
  keywords, topic and a per-chunk context line (Anthropic's Contextual
  Retrieval: −35% top-20 retrieval failures, −49% with BM25, −67% with a
  reranker). Local alternative to measure against it: **late chunking**
  (encode the whole file, pool per chunk) — works best with mean-pooling
  models, to be checked per candidate.
- Current chunk stats (1779 chunks, 2026-09-24): prose loses the most text to
  truncation (22% of its tokens), then lists and tables (17% each) — the
  problem is the word-based limit in general, not tables specifically.

*Design:*
- **Data model — SQLite is the source of truth; a vector store mirrors it**
  (Qdrant in Stage 3 gets the same fields as payload). `nodes`: three levels
  `doc → section → block` (block = paragraph, list-item group, or table-row
  group with the header row repeated; an oversize paragraph splits on
  sentence boundaries), with `parent_id`, `ord`, `heading_path`,
  `section_no`, `line_start`/`line_end`, `text`, `token_count`, `lang`,
  `content_hash`. Per-document metadata: `title`, `tags`, `date`, `updated`,
  `status`, `folder`, `privacy` (folder-derived), `superseded_by`, `summary`,
  `keywords`, `topic`. `links`: source, target, anchor, kind (markdown link,
  wikilink, path mention), with backlinks derived. Chunker and model versions
  are recorded in `meta` under the same `--rebuild` guard as the model today.
- **Vectors** on blocks; section- and document-level vectors (title +
  summary + keywords) as a measured variant. **FTS5** over block text,
  heading path and keywords for names and exact terms.
- **Retrieval (Samwise v2):** hybrid dense + FTS5 fused with RRF, filtered by
  privacy / `superseded_by` / folder / date → **reranker** (top-20/30 →
  top-5) → **context expansion** under a token budget: hit block ± neighbours;
  two or more hits in one section, or a short section → the whole section;
  several section hits in a short file → the whole file → **1-hop links**
  (outgoing + backlinks of the top files), included only when the linked file
  itself scores well for the query → a context bundle with citations (path +
  line range).
- **Enrichment runs under the Claude subscription, not the API:** a dedicated
  headless agent (`claude -p`) pinned to Haiku, returning structured output.
  Per-file (one call: summary, keywords, topic, a context line per section)
  vs. per-chunk is measured in phase D — the hypothesis is per-file, since
  each `claude -p` start has seconds of overhead and ~280 calls beat ~2000;
  measured as wall time and subscription usage. Results are cached by content
  hash, so an incremental commit costs 1–3 calls. Order is enrich → embed,
  since the context line goes into the embedding. Without an LLM the engine
  falls back to an extractive summary (title + heading path + first
  paragraph). Privacy: in the MVP the enrichment agent may see `core/` and
  `current/` — a deliberate, owner-approved use of the MVP exception.
- **Portable engine from phase C on:** configuration from outside (corpus,
  include/exclude, privacy map, model, enrichment provider) and swappable
  components — chunker, enricher (`claude-cli` / API / local / none),
  embedder, vector store (SQLite now, Qdrant in Stage 3), reranker,
  retriever. The engine knows nothing about brain/; Bilbo and Samwise become
  thin adapters (CLI + brain/ config). Moving it to its own repo later is a
  directory move plus `pip install`. Directory layout proposed for approval
  at phase C; no separate repo in this stage.

*Phases — each change is accepted only if it improves the eval:*
- [x] **A — Eval v2.** Golden set grown to ~60 queries in
      `brain/_meta/eval/samwise-golden.jsonl` (drafted by Claude from brain/
      content, verified by the owner; never in this repo). Query types: point
      lookup PL and EN, cross-lingual, multi-file, deep inside a long file,
      via a link, table/number, name/entity. New fields: `type`,
      `expected_sections`, `answer_snippet` (must appear in the returned
      context — measures expansion). Metrics: hit@1, MRR, recall@5 at file
      and section level; answer coverage at a token budget; context tokens;
      query latency p50/p95 on the Pi; build time; RAM. Harness builds and
      evaluates experimental indexes side by side with the production
      `bilbo.db`.
      **Done 2026-09-24.** Golden set: 63 queries (20 old + 43 new, owner-
      approved; 34 PL / 9 EN new). Harness: `index.py --db`,
      `run_eval.py --index/--strategies/--json-out/--quiet`, new metrics
      listed above. **Baseline v2 (MiniLM, production index, 1782 chunks):**

      | strategy | hit@1 | hit@5 | MRR | R@5 | sec@5 | ans@5 | p50 ms |
      |---|---|---|---|---|---|---|---|
      | grep | 0.30 | 0.62 | 0.42 | 0.57 | — | — | 40 |
      | semantic | 0.60 | 0.81 | 0.69 | 0.76 | 0.58 | 0.49 | 128 |
      | hybrid | 0.52 | 0.86 | 0.67 | 0.81 | 0.42 | 0.35 | 135 |

      The old 20 queries still score 0.70 / 0.725 (unchanged). Semantic's
      weak spots: `deep` (hit@5 0.38 — the truncation this redesign targets)
      and `multi` (0.44); grep is 1.00 on `deep` but 0.12 on `cross`, which is
      the case for hybrid retrieval. Only half the answers reach the reader
      (ans@5 0.49). F1-optimal threshold 0.5128; peak RSS 1.1 GB.
- [ ] **B — Model bake-off** on a simple structural chunker (no word limit):
      MiniLM (baseline), multilingual-e5-small, granite-97m-r2,
      arctic-m-v2.0, granite-311m-r2 — quality and Pi encode time. Ends with
      the model decision (`--rebuild`, threshold recalibration — which also
      closes the 0.5047 vs 0.5454 drift above).
- [ ] **C — Hierarchical index:** nodes, metadata, links, FTS5 hybrid,
      context expansion, Samwise v2 returning context bundles.
- [ ] **D — Enrichment ablation:** heuristic headers vs. late chunking vs.
      Haiku per-file vs. Haiku per-chunk.
- [ ] **E — Reranker (in this stage, not Stage 3):** bge-reranker-v2-m3
      (568M), gte-multilingual-reranker-base (306M), Qwen3-Reranker-0.6B —
      quality and Pi latency. Gains are expected to be small at today's
      scale; the component and its measurement are in place before brain/
      grows.

Sources: PL-MTEB (ACL 2026 Findings); IBM Granite Embedding Multilingual R2
model card; Snowflake Arctic Embed 2.0; Qu et al., "Is Semantic Chunking
Worth the Computational Cost?" (NAACL 2025 Findings); Anthropic, "Contextual
Retrieval"; Günther et al., "Late Chunking" (arXiv 2409.04701).

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
  side (Samwise, Step 3) is now built and consuming this index. Running on the
  Pi since 2026-09-22. Still open, now split into three tracks: automatic
  triggering (commit hook), chunking v2, and the Qdrant + reranker RAG —
  see the parking lot.
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
  Analysed exclusively through G.I.M.L.I. (owner/analytical access model,
  documented in `brain/db/CLAUDE.md`). Auto-discovered by Gimli via `brain/db/*.db` glob —
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

- [x] **E10 — `develop-idea` skill (2026-09-13).** Turns one raw project idea
  (pasted text, or a `backlog/projects/<slug>.md` reference) into a researched
  dossier at `knowledge/projects/<slug>.md`: feasibility assessment, web
  research on existing solutions/prior art, a proposed execution scenario,
  future expansion ideas, and a skill-growth assessment personalized against
  `core/identity/profile.md`/`goals.md`. Formalises and supersedes the
  raw-copy "promote" action in `/idea list` for ideas worth researching before
  starting; that raw-copy path still exists for trivial items. Structural
  precedent: `analyze-offer` (multi-section dossier, Stage/Decision lifecycle,
  update-in-place, compact-on-abandon). One new wrinkle worth noting: the real
  `brain/knowledge/projects/` already held 10 hand-written reference pages for
  shipped repos before this skill existed — a different, simpler content type
  (no `kind` field, typically `privacy: public`) now sharing the folder with
  this skill's dossiers (`kind: idea-dossier`, always `privacy: private`).
  Resolved with a `kind` field plus a hard-stop collision check rather than
  reshuffling the folder. → `.claude/skills/develop-idea/SKILL.md`,
  `.claude/brain-skeleton/knowledge/projects/CLAUDE.md`.

- [x] **E11 — `practice-prep` / `practice-review` skills (2026-09-18).** A
  prep/review loop for role-play practice with an external assistant (Gemini
  Live): mock interviews, explain-to-a-junior and explain-to-business drills.
  `practice-prep` (read-only) emits a paste-ready evaluator prompt — how to
  judge and how to summarize — personalized from `knowledge/career/`
  (`mock-interviews/`, `skills-matrix.md`, `interview-log.md`); the user
  writes the role and goal. `practice-review` re-checks the transcript
  independently (the sparring assistant's verdict is input, not ground truth),
  writes a record to `knowledge/career/mock-interviews/` and gated row notes
  to `skills-matrix.md` (never changes levels). Motivated by a session where
  an unprompted Gemini praised answers containing factual errors. Structural
  precedent: `english-prep` / `english-review`; language errors stay with
  those. → `.claude/skills/practice-prep/SKILL.md`,
  `.claude/skills/practice-review/SKILL.md`.

---

## Open decisions / parking lot

These points need a decision before or during the relevant step. Documented here
so they don't get lost.

| Decision | Relevant at | Options / notes |
|---|---|---|
| ~~**SQLite for MVP**~~ | ~~Step 1~~ | **RESOLVED 2026-06-26.** Real `dev_tracker.db` from `dev_activity_deamon` repo as smoke-test fixture; GIMLI is source-agnostic (registry: `brain/db/*.db` ∪ `GIMLI_EXTRA_DBS`). Postgres deferred to Phase 2 / Step 8. |
| ~~**Smeagol log destination**~~ | ~~Step 2~~ | **RESOLVED 2026-06-24.** JSONL, one file per day, in `brain/current/smeagol/`, written by a Stop hook. See Step 2 above. |
| ~~**Samwise Mode 1 → Mode 2 threshold**~~ | ~~Step 3 / Step 9~~ | **RESOLVED 2026-07-03 — moot.** Mode 2 (semantic, via Bilbo's index) shipped directly since Bilbo already existed; there was no Mode-1-first phase to graduate from. Mode 1 (grep) survives only as Samwise's fallback when the index is unavailable. |
| ~~**`brain/db/` access contract**~~ | ~~Step 4~~ | **RESOLVED 2026-09-18.** Gimli's "sole reader" monopoly was unworkable for operational databases (Faramir's dispatcher must ask "what is due now" of its own DB). Replaced by an owner model: each DB has one owner that writes (INSERT, idempotent upsert, state-column UPDATE; never DELETE) and runs fixed, pre-defined operational reads on its own DB; G.I.M.L.I. keeps the monopoly on analytical / ad-hoc SQL. External systems (n8n) never write — they notify the owner, which applies the change. → `brain/db/CLAUDE.md`, `.claude/agents/gimli.md`. |
| ~~**brain/ rules — single source**~~ | ~~Step 0~~ | **RESOLVED 2026-09-18.** Rule files were kept in two places (`.claude/brain-skeleton/` and brain/) and had drifted: 17 of them differed or existed on one side only. Root cause: Claude Code does not load `CLAUDE.md` from brain/ (a sibling directory, not part of the project tree — verified: nothing loads without `--add-dir` + `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`, and nested folder rules never load; an `@` import of a path outside the project does not load in headless `claude -p`), so skills pointed at the skeleton copy instead. Fix: brain/ is the single source (it describes itself, also for other tools); the skeleton keeps only data templates; `.claude/hooks/brain-instruction-sync/sync.py` injects brain/'s root rules at `SessionStart` and each folder's rules on the first Read/Edit/Glob/Grep there (Write: `PreToolUse`, whose context arrives together with the write result, not before it). Access via Bash does not trigger it. How it works, limits, and what to do when adding folders or debugging: `.claude/hooks/brain-instruction-sync/README.md`. |
| ~~**brain/ rules — scaffolding a new brain/**~~ | ~~Step 0~~ | **RESOLVED 2026-09-20.** Making brain/ the sole author of its rules broke the second supported setup path: `/init-brain` creation mode built a bare structure with no `CLAUDE.md` at all, so a new brain/ had no privacy levels, no frontmatter schema and no writer rules. Fix: the skeleton carries **bootstrap copies** of all 24 rule files — generic (personal examples and installation-specific databases stripped), copied only when a folder is created (`/init-brain` creation mode; `/daily`, `/idea`, `/english-review` for folders they create later), never read afterwards. Drift between the two copies no longer affects a live brain/ — it only makes a *newly created* brain/ slightly stale, and the hook always serves the brain/ version. Validation mode checks rule files for existence only and never restores them from the skeleton. Rejected alternative: exporting the snapshot from brain/ with a script + gitignored deny-list of private terms (built, then rolled back as premature — see git history of this branch if it is ever wanted). |
| **Phase 2 orchestration framework** | Step 7 | LangGraph vs LlamaIndex vs custom thin wrapper. Decided when the engine abstraction layer is built. |
| **Log-analysis role** | Step 2+ | **Partially resolved 2026-07-01.** R.A.D.A.G.A.S.T. (Step 2.5) covers the *reporting/analysis* half generically (trends, anomalies, comparisons over any data handed to it) — it could analyze Smeagol's logs like any other input, once something feeds them to it. Still open: whether a dedicated FTS5 retrieval layer over Smeagol's logs (E3) is needed before that's useful, or Radagast + ad-hoc `brain/current/smeagol/` reads suffice. |
| ~~**`brain/` privacy in MVP**~~ | ~~Step 1–3~~ | **RESOLVED 2026-06-09.** Private content may enter the Claude API context window in MVP. See § "Privacy in the Claude-API MVP". Tightened in Phase 2 (Step 7). |
| **Gateway transport & channels** | E1 | Which messaging platforms to support first; how to correlate a conversation thread across channels; where session context is held between messages. |
| **Skill-authoring heuristic** | E4 | What conditions trigger "this workflow should become a skill" — what qualifies, minimum reuse threshold, and who reviews before it is promoted to `prompt-vault`. |
| **Profile self-update guardrails** | E5 | What the automated system is allowed to write or overwrite in `core/profile.md`; append-only vs field-specific rules; how proposed updates are surfaced for human review before committing. |
| **Summary-sufficiency heuristic** | E8 | Bilbo/Samwise split is settled (matches README: Bilbo non-reactive indexer, Samwise reactive retriever). Step 3 established a precedent worth reusing here: a fixed similarity threshold (0.5047, F1-calibrated) works for point-lookup queries but measurably fails broad/enumerative ones (0/3 recall on two golden-set queries even ungated) — so E8's "summary vs. fetch full file" rule should not be a bare score cutoff either. Still open: the actual decision rule (threshold + query-intent classification, most likely) and whether it needs the same point-lookup/broad-query judgment split Samwise now does. Decided when E8 is implemented. |
| ~~**Bilbo trigger mechanism**~~ | ~~Step 9~~ | **RESOLVED 2026-09-24.** `post-commit` + `post-merge` hooks in `.claude/hooks/brain/` (brain/'s existing `core.hooksPath`, so the hooks are version-controlled here — no systemd units, nothing in `pi-automate`). Each starts `index.py --if-new-commits` detached, guarded by `flock -n`; `meta.last_indexed_commit` records the indexed HEAD. The 2026-09-22 direction included a debounce; dropped for now as premature — added only if bursts of commits prove costly. → `.claude/scripts/bilbo/README.md` § Automatic reindex on commit. |
| ~~**Chunking v2**~~ | ~~Step 9~~ | **SUPERSEDED 2026-09-24 by Index v2** — the word-limit fixes it listed (token-based limits, heading breadcrumbs, table-aware splitting, merging tiny sections) are folded into a hierarchical index with a model swap, enrichment and a reranker. See Step 9 § Index v2. |
| **Vector store: Qdrant** | Step 9 | **Direction set 2026-09-22: Qdrant.** (The reranker moved into Index v2, 2026-09-24.) Stated motivation is explicitly testing and portfolio ("a RAG on an RPi"), not throughput — at ~1.8 k chunks a numpy brute-force scan is already ~1 ms, so performance is not an argument. Real technical gains: payload filtering (privacy level, `superseded_by`, folder), the `kb_*` collections from README, native hybrid (dense + sparse) search, and a service n8n can reach. Open: **ChromaDB** — named in README as the Phase-2 store — has not been weighed against Qdrant yet; `kb_<folder>` collections vs. a single collection with a `folder` payload. Must-check first: the `qdrant/qdrant` image on this Pi's **16 KB-page** kernel (`getconf PAGESIZE` = 16384) — jemalloc has failed on that page size before. |
| ~~**Private golden set for eval**~~ | ~~Step 9~~ | **RESOLVED 2026-09-22.** The golden set paired real questions with the real files that answer them — together a description of brain/'s contents, in a public repo. It had been rewritten once to strip personal content, which left 6 of its 20 entries pointing at targets that no longer resolved, silently dragging every metric down and making the 2026-09-22 run incomparable with 2026-07-03's. Fix: the set lives in **brain/`_meta/eval/samwise-golden.jsonl`** (private by folder), resolved by `run_eval.py` via `$BRAIN_PATH` or a `SAMWISE_GOLDEN` override, with a synthetic `golden.example.jsonl` kept here purely to document the format. Note: earlier revisions of the set remain in this repo's git history — rewriting that history is a separate decision. |
