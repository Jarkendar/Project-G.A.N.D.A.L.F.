# USE-CASES.md — G.A.N.D.A.L.F. use cases

**Status:** living document. Content originates from the project owner's own
scenarios (informal, first captured 2026-06-25), translated and normalized here.
Add a new entry when a new need appears; update status tags as things get built.

**Relation to other docs:** README.md is the vision (why). IMPLEMENTATION.md is the
execution path (how/when). This file is the **demand signal** in between — concrete
scenarios that justify (or don't yet justify) work in IMPLEMENTATION.md. Read in that
order: README → USE-CASES → IMPLEMENTATION.

**Status legend:** ✅ have · 🟡 partial · ⬜ planned / not started.

Last updated: 2026-06-25.

---

## Platform rules

Two cross-cutting constraints. Not single-answer use cases — every use case below
depends on them holding true.

### R-1 — `brain/` sync discipline

`brain/` is read and written from more than one machine. To avoid conflicts and stale
reads: **always `pull` before a commit, always `push` after a commit.** Should be
enforced procedurally wherever a skill or agent writes to `brain/` — Claude Code can
handle most of this as a step inside the relevant skills, not as manual discipline.

**Status:** 🟡 partial — followed as a convention; not yet enforced as a hook or
skill step.

### R-2 — Gandalf reachable from anywhere

Gandalf must be reachable from any device on the local network or a virtual LAN
(Tailscale), not tied to whichever machine happens to be running Claude Code at the
time. Target host: a Raspberry Pi (cheap to run continuously, simplifies wiring into
existing `pi-automate` automations). Input channels: SSH, a messenger (Telegram),
ideally dictation/voice. Claude Code's own remote-control features cover part of this
today; a dedicated management app may end up being necessary.

**Status:** 🟡 partial — Claude Code remote-control gives partial coverage today;
RPi hosting depends on Step 8, messenger/voice input depends on E1 and Step 11.

---

## Use case catalog

Ordered roughly by implementation readiness and usefulness, not by capture order.
Each entry: scenario, what it touches in the existing architecture, current status.

### UC-1 — Daily journal with automatic routing

*User wants a free-form log of what happened during the day, what changed, what they
did. The system parses it and updates the right place itself.*

- **Maps to:** `/daily` skill — already dispatches to `/update-core`, `/add-contact`,
  `/idea`, and keeps an append-only monthly/yearly journal in `current/daily/`.
- **Open question:** does routing already cover health (UC-3) and learning-progress
  (UC-7) notes, or does it need new target categories?
- **Status:** ✅ have (mechanism) · 🟡 partial (domain coverage to verify).

### UC-2 — Contact & relationship notes

*User wants notes on friends/acquaintances — from basic contact info to deeper
personal context — broad enough to re-orient quickly after the generalities are
trimmed. Covers everyone the user has had contact with, organized into sections and
tags. Tags could potentially build a relationship graph.*

- **Maps to:** `add-contact` skill — index row + optional per-person detail file in
  `core/contacts/`, seeded with real data in Step 0.
- **Maps to (principle):** append-only with `superseded_by` — old facts aren't
  deleted, just superseded; long history stays recoverable.
- **Gaps:** tag support not yet confirmed against the current schema; a relationship
  graph built from tags is a new, unscoped capability.
- **Status:** ✅ have (core mechanism) · ⬜ planned (tags, graph).

### UC-3 — Health tracking & checkup recommendations

*User wants continuous monitoring of weight, fitness, injuries and pain, kept as a
journal that supports long-term conclusions. Also wants recommendations for which
medical checkups make sense given age, weight, occupation and training load.*

Two distinct halves:
1. **Logging + trend analysis** — source data lives in `core/health/` (`health.md`,
   `body.md`, `fitness.md`, templated since Step 0). Trend questions ("how has my
   weight moved since January") are `GROUP BY`-shaped — a Gimli candidate once the
   data is structured enough; markdown for now.
2. **Checkup recommendations** — not retrieval; needs external medical guidance
   cross-referenced against the user's profile. Closer to Legolas (web search) or
   Gandalf synthesis than to a data agent.

- **Feeds:** UC-6 (sports coaching) and UC-8 (diet), which both need current health
  state before proposing a plan.
- **Privacy:** PRIVATE (`core/`).
- **Status:** 🟡 partial (templates exist, no journaling/trend skill yet) · ⬜
  planned (recommendation logic).

### UC-4 — Financial research & strategy assistant

*User actively grows capital and wants help researching, analysing and choosing
instruments, and learning new domains/instruments. Wants the assistant to judge
whether a "whim" fits the existing strategy, help build the strategy together, and
propose steps toward the user's goals — with stewardship over the underlying data.*

- **Maps to:** **E7** (structure in place since 2026-06-12) — `core/finance/finance.md`
  (positions, strategy), `knowledge/finance/<TICKER>/` (dated reports),
  `knowledge/finance/analyses/` (pre-decision deliberations). E7's three planned
  skills (report ingestion, pre-investment analysis, portfolio report) cover part of
  this scenario.
- **New beyond E7:** learning a new domain/instrument (research → Legolas), judging
  fit against strategy, co-authoring the strategy itself — advisory, not just
  ingest-and-report.
- **Privacy:** PRIVATE, git-synced (`brain/`).
- **Status:** 🟡 partial (E7 structure + skills planned) · ⬜ planned (advisory
  layer).

### UC-5 — Career journal

*User wants a log of problems hit at work, how they were solved, and what needs
learning — feeding a future CV and ongoing skill-building.*

- **Maps to:** `knowledge/career/` — already exists (the `analyze-offer` skill writes
  job-offer dossiers there); a natural home for a career-journal subtree.
- **Connects to:** UC-7 (learning coach) for the "what needs learning" half; `/daily`
  (UC-1) as a possible routing target for free-form entries.
- **New capability:** building a CV from accumulated journal entries — no existing
  agent or skill covers this; closest conceptual fit is the unscoped L.I.N.D.I.R.
  content-drafting sketch.
- **Status:** ⬜ planned.

### UC-6 — Sports & training coaching

*User trains several sports/disciplines with varying experience in each. Needs a
coach that assesses progress, health state and predispositions, and proposes specific
workouts — or standalone advice, if preferred — plus occasional suggestions for new
activities.*

- **Depends on:** UC-3 (health/injury data, for safety) and the already-wired
  **Strava MCP** (real activity data as input to progress assessment).
- **Shape:** assess state (data + domain knowledge) → propose plan/advice → track
  outcomes → adjust. Same shape as UC-4, UC-7, UC-8 — see the note at the end of this
  catalog.
- **Status:** ⬜ planned.

### UC-7 — Domain learning coach

*User wants to learn a new domain (technology, science, hobby, any topic) but doesn't
know how. Needs a teacher that introduces general concepts, helps pick a learning
path, then proposes a detailed plan broken into modules and lessons; supervises
progress, difficulties and strengths, and adapts. Must track the user's learning
style as metadata and keep it updated.*

- **Maps to:** **E5** (evolving user profile) for the learning-style metadata —
  manual foundation is in place; agent-curated updates are the next increment.
- **New structure needed:** plan/module/lesson breakdown, progress journal — similar
  shape to `current/daily` journaling and to IMPLEMENTATION.md's own
  step/checkbox tracking.
- **Status:** ⬜ planned.

### UC-8 — Nutrition transformation & recipe memory

*User wants a dietary transformation — states a goal, liked and disliked foods. The
system proposes a balanced diet from saved recipes, preferences and goals, suggests
recipes, and saves the ones the user likes.*

- **Depends on:** UC-3 (health/weight goals) for the target; an existing `brain/`
  recipes concept (referenced informally in earlier sessions) as prior art.
- **New capability:** saving a liked recipe — a write-skill on the model of
  `add-contact`, but for recipes; doesn't exist yet.
- **Status:** 🟡 partial (recipes as data exist) · ⬜ planned (proposal + save flow).

### UC-9 — White Council: multi-perspective deliberation

*User facing a hard life/career decision, own view coloured by emotion, wants several
distinct points of view. A council of specialist personas, each with a different
approach, debates over several rounds and returns a verdict — decision, justification,
and a summary of each member's position. Personas must also be reachable
individually, as standing authorities — mentor, "gandalf", trainer, teacher — not
just as a council.*

- **Maps to:** **Step 6 — White Council**, currently a single line in
  IMPLEMENTATION.md; this scenario is the first concrete spec for it (debate
  protocol, verdict format, standalone persona access).
- **Connects to:** the coaching-shaped use cases above (UC-6 "trainer", UC-7
  "teacher") look like the same persona mechanism used in two modes — consulted
  individually for ongoing coaching, or convened together for a hard cross-domain
  decision.
- **Open questions (not resolved here):** how personas get named (Tolkien convention
  vs. a separate naming layer), and whether "talk to Gandalf as a persona" is
  distinct from talking to the orchestrator normally.
- **Status:** 🟡 partial (role named in roadmap, no spec) — this UC now provides one.

### UC-10 — Self-improving skills loop

*User frequently delegates similar tasks that share a common core. Wants the system
to notice this and automatically build a skill that streamlines the work.*

- **Maps to:** **E4 — Self-improving skills loop**, already documented as dependent
  on Step 6 (White Council validates the agent/skill split first) — i.e. UC-9 above
  is a prerequisite for this one.
- **Open question already tracked:** the "Skill-authoring heuristic" parking-lot
  decision (what qualifies, reuse threshold, review gate).
- **Status:** ⬜ planned.

---

## Cross-cutting pattern: the coaching loop

UC-4 (finance), UC-6 (sports), UC-7 (learning) and UC-8 (nutrition) share one shape:

**assess current state (personal data + domain knowledge) → propose a plan or
recommendation → track outcomes over time → adjust the next recommendation.**

Building this four times as four bespoke agents would duplicate the same machinery
four times. It fits the existing rule that skills orchestrate agents and agents don't
call each other directly: the coaching loop reads like **one skill, parametrized by
domain**, orchestrating Samwise (domain data in `brain/`), Legolas (external domain
knowledge), Gimli (once domain data is structured enough to query), and Faramir
(turning a recommendation into a tracked reminder/follow-up). No single existing or
proposed agent is itself "the coach" — that argues for keeping it a skill, not adding
a ninth agent.

This is a design observation to weigh when these use cases move into
IMPLEMENTATION.md, not a decision made here.

---

## Candidate use cases (not yet scenarios — flagged for consideration)

Surfaced while reviewing the catalog above; not yet written as scenarios by the
project owner, so not numbered as UCs. Listed so they aren't lost — drop any that
don't hold up.

- **Cross-domain consistency check** — before acting on one domain's recommendation,
  check it against adjacent domains (e.g. don't propose a heavy training block while
  an injury is logged per UC-3).
- **Unified periodic life report** — generalizes the existing weekly/monthly
  dev-activity report pattern (`dev_activity_daemon` → n8n) across all domains, not
  just dev time.
- **Decision / lessons-learned log** — generalizes UC-5's career-journal shape to
  other domains (finance, training decisions).
- **Commitment tracking** — recommendations like "redo bloodwork in 3 months" (UC-3)
  need to become tracked follow-ups, not just text in a past answer — ties to
  Faramir.
- **Time-allocation cross-reference** — Smeagol logs + `dev_tracker.db` + journal
  entries together answer "where does my time actually go" — a clean Gimli use case
  across sources.
