# 🧙 G.A.N.D.A.L.F.

**G**enerative **A**gent **N**avigating **D**atabases **A**nd **L**ocal **F**iles

> A local-first, multi-agent personal AI assistant running on Raspberry Pi 5.
> An attempt at building my own J.A.R.V.I.S. — minus the billionaire and the Iron Man suit.

---

## ⚠️ Project status

**The MVP is running on Claude Code** (updated 2026-11-05). Gandalf is a router in the main thread, the agents are Claude Code sub-agents, the engine is the Claude API. Built so far: the router and about two dozen agents, 21 skills, ten MCP servers, a RAG over the private `brain/` (Qdrant), query logging, a calendar agent, a White Council of personas, and agents that keep the owner's records, finance, training and learning. Not built: the local engine (Ollama), the move to the Pi as the sole host, the archivist (Treebeard), reminders and delegation (Faramir), the gateway and voice. The execution path with dates and open items lives in [IMPLEMENTATION.md](IMPLEMENTATION.md).

The README remains the *direction*, not the specification: the vision sections (knowledge base, memory hierarchy, potential paths) are canon and change only by the owner's decision, while status, the agent table and the graphs follow what is built.

---

## 💡 Motivation

This project exists for four reasons, in roughly this order:

1. **Learn.** Modern multi-agent systems, RAG, agentic workflows, and on-device LLMs are reshaping how software is built. The best way to understand them is to build one from scratch.
2. **Build my own J.A.R.V.I.S.** The Tony Stark assistant fantasy is unattainable in full, but a stripped-down personal version — one that knows my projects, my data, and my context — is achievable today on consumer hardware.
3. **Own the stack.** Most useful AI tooling sends private data to third-party APIs. A local-first system keeps personal context (notes, finances, relationships, health) on hardware I control.
4. **Use the hardware I already have.** A Raspberry Pi 5 and a desktop with an RTX 2070 Super are sitting in my homelab. They're capable of running this — they just need the right software.

---

## 🏷️ A note on naming

All components in this system follow a `X.Y.Z.` acronym format, and yes — the names are Tolkien references. This is a deliberate convention, not an accident:

- The acronym always describes the component's **role** (e.g. `G.A.N.D.A.L.F.` = *Generative Agent Navigating Databases And Local Files*).
- The character chosen reflects the component's **disposition** — Samwise carries weight, Gimli digs through structured data, Legolas scouts the outside world, Treebeard remembers everything from long ago.
- The metaphor fits the hardware: a small Raspberry Pi shouldering a large workload, a fellowship of specialised agents instead of one all-knowing model.
- **Skills** follow a different convention — they take their names from Tolkien **events or groups** (the *White Council*, the *Last Alliance*) rather than single characters, because a skill is plural by nature.

If a name feels forced, the role probably needs rethinking.

---

## 🏛️ Architecture

G.A.N.D.A.L.F. is built as a **router + specialised sub-agents** pattern, with an optional **skills layer** for higher-order workflows that orchestrate multiple agents. The main orchestrator does not try to know everything — it classifies incoming requests, routes them to a single agent or a skill, and synthesises the final answer.

The architecture is intentionally open to **multiple orchestrators** in the future. Gandalf is the first one — a generalist router for personal queries — but specialised orchestrators (for example, a dev-focused or a homelab-focused one) can co-exist and federate. For now there is one Gandalf and the rest is intentional headroom.

The router is a main-thread Claude Code agent that holds the conversation and carries questions and answers between the owner and the sub-agents (a sub-agent cannot ask the owner itself). The graphs below show the system as built on 2026-11-05; dashed boxes are planned.

### Graph 1 — who talks to whom

```mermaid
flowchart TD
    User["👤 Owner<br/><i>text</i>"]
    Gandalf["🧙 G.A.N.D.A.L.F.<br/><b>router</b><br/><i>classify · route · ask · confirm</i>"]

    subgraph Questions["🔎 Questions and reports"]
        Samwise["🧑‍🌾 S.A.M.W.I.S.E.<br/><i>semantic search</i>"]
        Gimli["🪓 G.I.M.L.I.<br/><i>read-only SQL</i>"]
        Radagast["🐦 R.A.D.A.G.A.S.T.<br/><i>reports</i>"]
        Erestor["📜 E.R.E.S.T.O.R.<br/><i>practice briefings</i>"]
    end

    subgraph Records["📓 Records and plans (write to brain/)"]
        Frodo["🧑‍🌾 F.R.O.D.O.<br/><i>days · ideas · profile · contacts</i>"]
        Balin["⛏️ B.A.L.I.N.<br/><i>career · English</i>"]
        Cirdan["⚓ C.I.R.D.A.N.<br/><i>project ideas</i>"]
        Strider["🥾 S.T.R.I.D.E.R.<br/><i>packing</i>"]
        Arwen["🧝 A.R.W.E.N.<br/><i>flashcards</i>"]
    end

    subgraph Coaches["🏋️ Trainers and teachers"]
        Glorfindel["G.L.O.R.F.I.N.D.E.L.<br/><i>training</i>"]
        Daeron["D.A.E.R.O.N.<br/><i>guitar</i>"]
        Rumil["R.U.M.I.L.<br/><i>learning</i>"]
    end

    subgraph Finance["💰 Finance"]
        Thorin["T.H.O.R.I.N.<br/><i>portfolio record</i>"]
        Dain["D.A.I.N.<br/><i>analyses</i>"]
        Gloin["G.L.O.I.N.<br/><i>public reports</i>"]
    end

    subgraph Council["🕊️ White Council"]
        Beorn["B.E.O.R.N.<br/><i>persona voice</i>"]
        Elrond["E.L.R.O.N.D.<br/><i>synthesis</i>"]
        Finrod["F.I.N.R.O.D.<br/><i>persona builder</i>"]
        Narvi["N.A.R.V.I.<br/><i>digests</i>"]
    end

    Legolas["🏹 L.E.G.O.L.A.S.<br/><i>web research</i>"]
    Faramir["🛡️ F.A.R.A.M.I.R.<br/><i>calendar</i>"]
    Aule["🔨 A.U.L.E.<br/><i>this repo</i>"]
    Ori["📦 O.R.I.<br/><i>commits brain/</i>"]
    Smeagol["👁️ S.M.E.A.G.O.L.<br/><i>Stop-hook logger</i>"]

    User <--> Gandalf
    Gandalf -.routes.-> Questions
    Gandalf -.routes.-> Records
    Gandalf -.routes.-> Coaches
    Gandalf -.routes.-> Finance
    Gandalf -.runs.-> Council
    Gandalf -.routes.-> Faramir
    Gandalf -.routes.-> Legolas
    Gandalf -.routes.-> Aule
    Gandalf ==every turn==> Smeagol

    Records -->|"paths written"| Ori
    Coaches --> Ori
    Finance --> Ori
    Finrod --> Ori
    Balin --> Legolas
    Cirdan --> Legolas
    Coaches --> Legolas
    Dain --> Gloin
    Thorin --> Gloin
    Finrod --> Narvi
    Coaches -.calendar events via the router.-> Faramir
    Rumil -.flashcard material via the router.-> Arwen

    Treebeard["🌳 T.R.E.E.B.E.A.R.D.<br/><i>archivist — planned</i>"]:::planned
    Gandalf -.-> Treebeard
    classDef planned stroke-dasharray: 5 5,color:#888
```

### Graph 2 — data, MCP servers and privacy

```mermaid
flowchart LR
    subgraph Brain["🧠 brain/ — private repo, sibling directory"]
        Core["core/ · current/<br/>🔒 PRIVATE"]
        Knowledge["knowledge/<br/>public"]
        Db[("db/*.db<br/>SQLite")]
        Conv["conversations/ · backlog/"]
    end

    subgraph MCP["🔌 MCP servers (.mcp.json)"]
        mSamwise["samwise (http)"]
        mGimli["gimli (read-only)"]
        mOri["ori"]
        mFrodo["frodo"]
        mBalin["balin"]
        mThorin["thorin"]
        mElrond["elrond"]
        mMirdain["mirdain"]
        mArwen["arwen"]
        mSync["sync"]
        mStrava["strava"]
    end

    subgraph Guards["🛡️ Guards (hooks)"]
        WG["write-guard<br/><i>per-agent write zones</i>"]
        BG["bash-guard"]
        FG["faramir-guard<br/><i>consent token</i>"]
        BIS["brain-instruction-sync"]
    end

    subgraph External["🌐 External"]
        Web["Web"]
        AnkiWeb["AnkiWeb"]
        GCal["Google Calendar"]
        StravaAPI["Strava"]
        Edgar["SEC EDGAR"]
        ClaudeAPI["Claude API<br/><i>the engine</i>"]
    end

    Agents["🧝 agents"] --> WG
    Agents --> mSamwise --> Core
    mSamwise --> Knowledge
    Agents --> mGimli --> Db
    Agents --> mFrodo --> Db
    Agents --> mOri -->|"commit · push, main only"| Brain
    Agents --> mBalin --> Conv
    Agents --> mThorin --> Edgar
    Agents --> mArwen --> AnkiWeb
    Agents --> mStrava --> StravaAPI
    Agents --> FG --> GCal
    Agents -->|"Legolas only"| Web
    Core -.->|"MVP exception"| ClaudeAPI
    Gandalf["🧙 router"] --> mSync
    BIS -.->|"folder rules into context"| Agents
```

Reading the privacy picture: `core/` and `current/` are private by folder, `knowledge/` is public. In the Claude-API MVP the engine itself may see private content (a conscious, time-boxed exception — see IMPLEMENTATION.md § "Privacy in the Claude-API MVP"); the only agent with the open web (Legolas) is given public names only, and cards that leave for AnkiWeb from private folders need the owner's explicit yes. Only Ori commits and pushes `brain/`, and only on `main`.

### Graph 3 — retrieval (RAG over brain/)

```mermaid
flowchart LR
    Commit["git commit / merge in brain/"] -->|"post-commit · post-merge hook"| Bilbo["🎒 B.I.L.B.O.<br/><i>hierarchical index v2</i>"]
    Bilbo --> Qdrant[("Qdrant<br/><i>imladris-rag</i>")]
    Qdrant --> Mcp["samwise MCP (http :8765)"]
    Mcp --> Rerank["reranker"]
    Rerank --> Router["🧙 router and agents<br/><i>context · search</i>"]
    Warm["samwise-warmup hook"] -.-> Mcp
    Router --> Files["Read the files<br/><i>paths relative to brain/</i>"]
```

### Graph 4 — a White Council

```mermaid
sequenceDiagram
    participant O as Owner
    participant G as Router
    participant B as Beorn x N (persona cards)
    participant E as Elrond
    participant K as knowledge/councils/
    O->>G: a hard decision, several voices
    G->>O: roster and question — confirm
    G->>B: the question, one call per voice
    B-->>G: each answer to a scratchpad file
    G->>E: the folder of answer files
    E->>K: synthesis + assembled record (record tool)
    E-->>G: summary
    G->>O: voices, disagreements, synthesis
```

Persona cards are built separately: Finrod runs the `persona` skill stage by stage (scope, sources, digests through Narvi, card, validation), and the cards live in `knowledge/personas/`.

### Engine layer

Underneath the agents sits an **engine** — the actual LLM doing the work. The MVP commits to a single choice for speed of iteration, with a planned abstraction layer once the system stabilises:

| Phase | Engine | Rationale |
|---|---|---|
| MVP | Claude Code / Claude API | Fast to build on, mature tool-calling, skills + sub-agents already work the way this project wants them to |
| Phase 2 | Abstraction layer + local models (Ollama) | Model-agnostic interface so any agent can run on a local model, the cloud, or both depending on cost/privacy/latency |

The local-first goal from the motivation is not abandoned — it's deferred. Getting the **shape** right first (skills, agents, knowledge base, routing) matters more than getting the engine right; engines are interchangeable, architecture is not.

---

## 🧝 The Fellowship — agents and skills

The fellowship splits into two layers:

- **Agents** are single-responsibility specialists. Each owns one narrow job and is named after a Tolkien character with the matching disposition, with the role encoded as an acronym (e.g. G.I.M.L.I. — *Generative Intelligence Mining Local Information*). Small local models perform well on narrow tasks and poorly on generic "do everything" prompts, which is why this layer exists at all.
- **Skills** are higher-order workflows that orchestrate multiple agents to deliver something none of them can deliver alone. Skills follow the event-or-group naming convention described above.

### Agents — what is built (2026-11-05)

Every agent is a Claude Code sub-agent with the narrowest tool list its job allows (Gandalf's own list is the router's: read, search, ask, call the agents below, a small write zone in the scratchpad, and read-only git tools). "Writes" names the only places an agent may write; a `write-guard` hook enforces it. Anything written to `brain/` is committed by Ori, never by the writer. Full definitions: `.claude/agents/`; per-agent rules for this repo: `.claude/rules/dev.md`.

**Router and retrieval**

| Agent | Acronym | Tasks / modes | Tools and access | Writes |
|---|---|---|---|---|
| 🧙 **G.A.N.D.A.L.F.** | *Generative Agent Navigating Databases And Local Files* | classifies, routes, holds the conversation, asks and confirms; quick public checks; runs a White Council; `pull` / `status` / `log` / `checkout_main` for both repos | Read · Grep · Glob · calls all sub-agents · Samwise · `WebSearch` / `WebFetch` (public names only) · `sync` MCP | scratchpad only; no commit, push or merge |
| 🧑‍🌾 **S.A.M.W.I.S.E.** | *SQL And Markdown Wading Into Semantic Embeddings* | semantic search over `brain/` (`context`, `search`) | MCP server over Qdrant, reranked | nothing |
| 🪓 **G.I.M.L.I.** | *Generative Intelligence Mining Local Information* | analytical SQL: sums, counts, trends | `gimli` MCP: `databases`, `schema`, `query` — read-only SQLite, results labelled with privacy level; model: haiku | nothing |
| 🐦 **R.A.D.A.G.A.S.T.** | *Reporting Agent Delivering Analysis, Graphs, Assessments, Summaries & Trends* | reports and charts from data handed to him | Read · Write | `knowledge/reports/` |
| 🏹 **L.E.G.O.L.A.S.** | *Local Engine Generating Outputs, Looking At Search* | web research; the forked helpers `research-offer`, `research-idea` | `WebSearch` · `WebFetch` only — no file tools | nothing |
| 📜 **E.R.E.S.T.O.R.** | *Evaluator Reading Earlier Sessions To Orient Rehearsal* | briefings before English or interview practice (`english-prep`, `practice-prep`) | Read · Grep · Glob | nothing |

**Records and plans (write to `brain/`)**

| Agent | Acronym | Tasks / modes | Tools and access | Writes |
|---|---|---|---|---|
| 🧑‍🌾 **F.R.O.D.O.** | *Filing Records Of Days & Observations* | `daily`, `idea`, `update-core`, `add-contact`, `interview` | Read/Write/Edit · Strava read tools · `fitness_upsert`, `now` · calls Ori | daily notes, backlog, `core/identity/`, contacts, fitness DB, learning method note |
| ⛏️ **B.A.L.I.N.** | *Briefs, Assessments & Lessons for Interviews and Negotiations* | `analyze-offer`, `practice-review`, `english-review` | Read/Write/Edit · `archive_transcripts` · calls Legolas, Ori | offer dossiers, practice records, English reviews, `conversations/` |
| ⚓ **C.I.R.D.A.N.** | *Concept Investigation, Research, Dossier, Assessment & Next-steps* | `develop-idea`: feasibility, prior art, execution scenario | Read/Write/Edit · calls Legolas, Ori | `knowledge/projects/` |
| 🥾 **S.T.R.I.D.E.R.** | *Supplies, Trips & Route Inventory, Drafted for Every Road* | `pack`: trip lists, post-trip reviews, item catalogue, packing profiles | Read/Write/Edit · calls Ori | packing records |
| 🧝 **A.R.W.E.N.** | *Anki Repetition & Web-sync Engine for Notes* | `flashcards`: drafts atomic cards, drops duplicates, adds on approval | Read · Samwise · `arwen` MCP (`list_decks`, `find_notes`, `add_notes`) | the Anki collection (synced to AnkiWeb); private-folder cards only on the owner's yes |

**Trainers and teachers** — each runs four tasks from his own instructions (plan, retro, adjustment, menu), writes a plan only on the owner's yes to a full plan, and sends calendar events through the router to Faramir.

| Agent | Acronym | Domain | Tools and access | Writes |
|---|---|---|---|---|
| 🏋️ **G.L.O.R.F.I.N.D.E.L.** | *Goal-Led Orchestration of Runs, Form, Intervals, Nutrition, Daily Effort & Load* | cycle and week training plans, weekly retro | Read/Grep/Glob/Write · Strava read · Samwise · calls Gimli, Legolas, Ori | `current/fitness/plans/` |
| 🎸 **D.A.E.R.O.N.** | *Deliberate Ear, Axe, Riffs, Orchestrated Practice & Notation* | guitar sprint plans, review, adjustments | Read/Grep/Glob/Write · Samwise · calls Legolas, Ori | `current/guitar/plans/` |
| 📚 **R.U.M.I.L.** | *Reps, Understanding, Mnemonics, Inquiry & Lore* | topic bank, week plans of ~30-minute sessions, Sunday retro | Read/Grep/Glob/Write/Edit · Samwise · calls Legolas, Ori | `current/learning/` (plans, `topics.md`) |

**Finance**

| Agent | Acronym | Tasks / modes | Tools and access | Writes |
|---|---|---|---|---|
| 🏔️ **T.H.O.R.I.N.** | *Treasury Holdings & Official Reports INgest* | `ingest-finance` — only on the owner's explicit word | Read/Write/Edit · `read_export`, `archive_export` · calls Glóin, Ori | `core/finance/finance.md`, archived export |
| 📈 **D.A.I.N.** | *Decisions, Analyses & Investment Notes* | earnings review against the thesis, pre-investment, event calendar, rebalancing against the thesis' own triggers; gives no recommendation without the owner's thesis | Read/Grep/Glob/Write/Edit · calls Glóin, Legolas, Ori | `knowledge/finance/analyses/` |
| 🧾 **G.L.O.I.N.** | *Gathering Ledgers Of Issuers' Numbers* | fetches public company reports (`fetch-finance-reports`) | `WebFetch` · `edgar_reports` MCP · Write — no shell | `knowledge/finance/<TICKER>/` |

**White Council and persona building**

| Agent | Acronym | Tasks / modes | Tools and access | Writes |
|---|---|---|---|---|
| 🐻 **B.E.O.R.N.** | *Bearer of Embodied Opinions, Roles & Natures* | speaks as one persona card; model: opus for fidelity | Read · Grep · Glob · `samwise context` | one answer file in the scratchpad |
| 🧝‍♂️ **E.L.R.O.N.D.** | *Examiner Laying out Rounds' Outcomes, Noting Dissent* | closes a Council: synthesis and the assembled record | Read · Glob · Write · `elrond` `record` | `knowledge/councils/` |
| 🌟 **F.I.N.R.O.D.** | *Faithful Images of Notable Reasoning, Opinions & Decisions* | builds a persona stage by stage: scope, sources, digests, card, validation (`persona` skill) | Read/Grep/Glob/Write/Edit · `mirdain` MCP · calls Narvi, Legolas, Ori | `knowledge/personas/` |
| ⚒️ **N.A.R.V.I.** | *Note-taker Abstracting Reasoning, Views & Idiom* | persona digest drafts | Read · Write — no shell | `.md` in the temp directory only |

**Calendar and repository**

| Agent | Acronym | Tasks / modes | Tools and access | Writes |
|---|---|---|---|---|
| 🛡️ **F.A.R.A.M.I.R.** | *Forwarding Actions, Reminders And Meetings, Invoking Repositories* | reads the main and shared calendars, creates events (titles marked `[Gandalf]`); reminders and delegation to the forge are not built yet | Google Calendar connector only; no `brain/` access; deletes, edits and events with guests need the owner's yes (consent-token hook) | the main calendar |
| 🔨 **A.U.L.E.** | *Agent Updating Logic & Ecosystem* | changes to this repo: agents, skills, routing, hooks, scripts, docs — plan first, then branch, commits, PR; never merges | Read/Grep/Glob/Write/Edit · Bash behind a guard | this repo, on a branch |
| 📦 **O.R.I.** | *Orderly Record Inscriber* | commits and pushes `brain/` — the only agent that may; main only; model: haiku | `ori` MCP: `status`, `commit` | git history of `brain/` |

**Scripts and hooks (not reactive agents)**

| Component | Acronym | Role |
|---|---|---|
| 🎒 **B.I.L.B.O.** | *Bot Indexing Local Binary Objects* | embedding indexer; reindexes on every commit or merge in `brain/` through git hooks |
| 👁️ **S.M.E.A.G.O.L.** | *Storage Module Evaluating All Gandalf's Operational Logs* | Stop-hook that logs every turn to `brain/current/smeagol/` — writes the log, never reads it |

**Planned or only proposed** — placeholders to be revisited once Smeagol's logs reveal which gaps matter. None of these names is a commitment.

| Role | Status | Name | Notes |
|---|---|---|---|
| Archival, compression, historical retrieval | planned (Step 10) | **T.R.E.E.B.E.A.R.D.** | *Temporal Repository Engine Evaluating, Archiving And Reducing Data* — meaningful once 6–12 months of data accumulate |
| Personal advisor (single voice) | proposed | **G.A.L.A.D.R.I.E.L.** | *Guidance Agent for Life Alignment: Decisions, Reflection, Insight, Evaluation, Lookahead* |
| Content drafting | proposed | **L.I.N.D.I.R.** | *Language and Ideation Node for Drafting, Illustrating, Rewriting* |
| Outreach and lead research | proposed | **H.A.L.D.I.R.** | *Handling Active Lead Discovery, Intelligence, Research* |
| Multi-channel gateway and voice | planned (E1) | — | the dispatcher role Radagast once sketched is not what he does now |
| Log analysis and insight extraction | open | — | Radagast could read Smeagol's logs; a dedicated layer is E3 |
| Development task execution | external | [`agentic-sdlc-forge`](https://github.com/Jarkendar/agentic-sdlc-forge) | an external executor Faramir is to invoke — not built |

### Skills

Skills are the higher-order workflows; most are owned by one agent, which runs them. Built so far (21): `daily`, `idea`, `update-core`, `add-contact`, `interview` (Frodo); `analyze-offer`, `practice-review`, `english-review` (Balin); `english-prep`, `practice-prep` (Erestor, forked); `develop-idea` (Círdan); `pack` (Strider); `flashcards` (Arwen); `ingest-finance` (Thorin); `fetch-finance-reports` (Glóin, forked); `research-offer`, `research-idea` (Legolas, forked helpers); `persona` (Finrod); `council` (the White Council, run by the router); and two that only run in a full session: `init-brain`, `ingest-conversation`.

### The White Council and personas

The White Council is the first skill: several advisers, each a persona card spoken by Beorn, answer one hard decision independently, then Elrond writes a synthesis that keeps the dissent. The personas are built and validated against their sources by Finrod. They fall into broad groups — finance and investing, productivity and work, philosophy and the examined life, and Polish-language voices — and the aim is deliberately to hear angles the owner would not reach alone, including uncomfortable ones. The current roster and its history are in IMPLEMENTATION.md.

### Two roles worth a paragraph

**F.A.R.A.M.I.R.** is meant to be the bridge between G.A.N.D.A.L.F. (knowledge orchestration) and tools like [`agentic-sdlc-forge`](https://github.com/Jarkendar/agentic-sdlc-forge) or `n8n` workflows: when a request requires *doing something* rather than *knowing something*, he handles the handoff. Today only the calendar half exists; reminders and delegation are Step 4.

**L.E.G.O.L.A.S.** is the only agent with the open web. The search backend is still the built-in `WebSearch` / `WebFetch`; a self-hosted SearXNG remains the long-term target.

### 👁️ S.M.E.A.G.O.L.

**S**torage **M**odule **E**valuating **A**ll **G**andalf's **O**perational **L**ogs

Smeagol's job ends at *writing the log*. He doesn't analyse it. The system improves by reading its own logs, but the *reader* is intentionally a separate role (see the planned table — a future log-analysis agent or skill, persona TBD). Keeping logging and analysis separate makes both replaceable.

### 🌳 T.R.E.E.B.E.A.R.D.

**T**emporal **R**epository **E**ngine **E**valuating, **A**rchiving **A**nd **R**educing **D**ata

The archivist. Old, slow, speaks at length, and remembers everything. Treebeard runs on a schedule (nightly or weekly) and performs three jobs that no other agent owns:

1. **Compression.** Groups of stale chunks within the same silo are summarised by a local LLM into a single condensed chunk — fifty daily notes from March collapse into one *"March 2026: worked on X, read Y, opinions on Z shifted from A to B"* chunk. Originals move to `brain/archive/`; the summary stays in the source folder (Phase 2+: in the active vector collection).
2. **Supersession resolution.** When a fact is updated (`superseded_by` pointer set), Treebeard decides whether the old version should remain individually retrievable (e.g. core profile or relationship history) or be folded into a periodic snapshot.
3. **Archive retrieval.** When Gandalf receives an explicitly historical query (*"what did I think about X two years ago?"*, *"how were my finances in 2024?"*), Treebeard is called instead of Samwise — he is the one with access to `brain/archive/`.

Treebeard is why the active knowledge base stops growing linearly after roughly two years of use. Without him, the system slowly drowns in its own past.

---

## 🧠 Knowledge base

The knowledge base is the hardest part of the project. Not because storing data is difficult — but because *organising personal context so that an AI can use it well* is an open problem. The design here is deliberately staged: start small, evolve as real usage reveals what's needed.

### Design principles

- **Privacy is tiered, not binary.** Some data should never leave the device under any circumstances. Other data can be sent to cloud models when needed. The split is enforced architecturally, not by convention.
- **Rate of change determines storage strategy.** Stable facts ("I live in Poland") and rapidly changing context ("what I read today") cannot share the same indexing logic.
- **Structure matters.** Bank exports belong in SQL, not in a vector database. Forcing everything into embeddings degrades both retrieval quality and answer correctness.
- **Not everything deserves embeddings.** Full PDFs, course HTML, and reference books are expensive to vectorise and produce noisy retrieval. They belong in cold storage with a thin searchable manifest pointing to them.
- **Evolutionary schema.** The initial structure will be wrong in unexpected ways. The system must be easy to refactor as real usage reveals what's missing.
- **Append-only with compression.** History has value, but unbounded growth does not. Old data is preserved as compressed summaries, not deleted.

### Phase 1 — A markdown brain in a git repo

The MVP knowledge base is a **separate `brain/` repository, mostly markdown files, version-controlled in git**. No vector database, no embeddings — at MVP scale they cost more than they pay back, and a flat tree of MD files is debuggable in a way a vector store never is. *(Status: the vector layer of Phase 2 was added anyway in September 2026 — Qdrant, a hierarchical index and a reranker, read through Samwise — once questions about "what did I plan" outgrew grep.)*

```
brain/
├── core/
│   ├── profile.md          # who I am, stable facts
│   ├── goals.md            # current goals & horizons
│   ├── projects.md         # active projects, status
│   └── contacts.md         # people, relationships, context
├── knowledge/              # topics, learning, references
├── current/                # daily notes, recent activity
├── conversations/          # exported AI conversations
└── archive/                # Treebeard's compressed summaries (Phase 2+)
```

Two top-level rules:

1. **Markdown by default.** If the data is text-shaped — notes, summaries, transcripts, profile info, project context — it goes into a `.md` file. Gandalf reads the files directly; no embedding layer needed at this scale.
2. **SQL only when the shape demands it.** Structured, high-volume, schema-stable data — bank transactions, dev-tracker telemetry, media consumption logs — goes into SQLite. The rule is simple: if you'd answer the question with `GROUP BY`, it belongs in SQL.

This collapses the earlier *public / private* zone split into something simpler: **privacy is a folder-level concern**, enforced by which folders local-only models are allowed to read. `core/` and `current/` are private; `knowledge/` is public.

### Phase 2 — Vectors, when they earn their keep

Once the brain repo passes a few thousand markdown files and direct retrieval starts feeling slow or noisy, S.A.M.W.I.S.E. adds an embedding layer **over** the existing files. The markdown stays canonical; the vector DB is just an index pointing back at it. Each top-level folder in `brain/` becomes a vector collection of the same name prefixed with `kb_` (so `brain/current/` indexes into `kb_current`, `brain/knowledge/` into `kb_knowledge`, etc.) — this is the naming used in the *Memory hierarchy* section below. B.I.L.B.O.'s scheduled-indexer role is deferred until this phase — at MVP scale, files change rarely enough that re-reading on demand is fine.

### Phase 3 — Domain silos & hybrid structures (when justified)

Once S.M.E.A.G.O.L.'s logs show which folders are actually queried, used, and useful, dedicated silos can be carved out — and more sophisticated structures can be added selectively:

- **Knowledge graph** layer for explicitly curated areas (projects, learning paths)
- **Time-aware retrieval** with recency boosting for fast-changing folders
- **Hierarchical retrieval** (search summaries first, fetch full content on demand)

Splits are driven by logged usage, not upfront design.

### Ingestion pipelines

Data has to get *into* the brain repo somehow, and almost none of it starts there. The pattern is the same in every case: an **external trigger** → an **n8n flow** → a **markdown file committed to `brain/`**. n8n is the glue; the brain repo is the destination. Concrete examples:

| Source | Pipeline | Lands in |
|---|---|---|
| **Voice notes** (phone, walking, dictation app) | recording → cloud sync → n8n watcher → Whisper STT → LLM summary → MD | `brain/current/voice/YYYY-MM-DD.md` |
| **Email** (newsletters, receipts, threads worth keeping) | forwarded to a dedicated address → n8n IMAP poll → strip + summarise → MD | `brain/knowledge/email/<topic>.md` or `brain/current/email/` |
| **Drive files** (PDFs, exports, scans) | new file in watched Drive folder → n8n download → text extraction → MD + cold file kept on disk | `brain/knowledge/<topic>/` + `brain/_blobs/` |
| **GitHub activity** (commits, PRs, issues from my repos) | webhook → n8n → grouped daily digest → MD | `brain/current/dev/YYYY-MM-DD.md` |
| **Quick capture** (links, thoughts, snippets from anywhere) | Telegram/Signal bot → n8n → MD with tags from the message | `brain/current/captures/YYYY-MM-DD.md` |
| **Calendar events** (meetings, decisions, attendees) | calendar webhook → n8n → templated MD (attendees, notes placeholder) | `brain/current/meetings/YYYY-MM-DD-<slug>.md` |
| **Watched folders** (Obsidian, Downloads) | direct filesystem sync — bypasses n8n | `brain/knowledge/` or `brain/current/` |
| **Manual** (paste, drop into folder, commit) | human writes/pastes MD | anywhere |

A few principles hold across all of them:

- **One source → one folder.** No fan-out. Voice notes don't end up scattered across three places; one folder per pipeline, easy to audit, easy to delete.
- **Raw + summary, never just summary.** When LLMs are involved (transcription, extraction), the original artifact is kept in `_blobs/` so summaries can be regenerated later.
- **Date-prefixed filenames.** `YYYY-MM-DD-<slug>.md` makes Treebeard's compression and retro queries trivial.
- **Idempotency.** Every n8n flow must be safe to re-run; the brain repo is git, conflicts are recoverable, but duplicate commits aren't.
- **No silent failures.** If a pipeline fails, an entry lands in `brain/_errors/` — visible, not hidden.

The deferred items (browser extension, drop-zone HTTP webhook) come later; they're variants on the same `→ n8n → MD` pattern, not new architecture.

---

## 🧬 Memory hierarchy

A single flat vector database is fine at 1 000 chunks and disastrous at 100 000. The memory model below separates data by **what kind of question it answers** and **how fast it goes stale**, then layers compression on top to keep the active footprint bounded over time. The `kb_*` names below refer to Phase 2+ vector collections that mirror the `brain/` folder structure.

### Three storage tiers

Data lives in one of three tiers, chosen by the *shape of questions* you'd realistically ask of it:

| Tier | Backend | Use when the question is… | Examples |
|---|---|---|---|
| **A — Structured** | SQLite | *how much / when / which / count* | Bank transactions, dev-tracker telemetry, media consumption log, life timeline |
| **B — Semantic** | Qdrant (vector; ChromaDB was the first sketch) | *what did I think / how does X work / find similar* | Notes, conversation summaries, article digests, project context |
| **C — Cold blobs** | Filesystem + SQLite manifest | *where is the original* | Full PDFs, course HTML, raw exports, source documents |

The cold tier is critical and easy to underestimate. Vectorising a 400-page book produces hundreds of low-quality chunks that pollute retrieval. Storing the file in `brain/_blobs/` and indexing only a 200-word LLM-generated summary plus metadata in the manifest gives Gandalf enough to say *"this is in `sapiens.pdf`, chapter 3 covers your question"* — which is usually what you actually want.

### Temporal layers — active, warm, archive

Inside the semantic tier, data also moves through age-based layers, managed by T.R.E.E.B.E.A.R.D.:

```
┌─────────────────────────────────────────────────────────────┐
│  ACTIVE     │  full-resolution chunks, recent               │
│             │  (last N days/months, silo-dependent)         │
│             │  → primary retrieval target for Samwise       │
├─────────────────────────────────────────────────────────────┤
│  WARM       │  chunks past first threshold, not yet         │
│             │  compressed                                   │
│             │  → still retrievable, lower recency score     │
├─────────────────────────────────────────────────────────────┤
│  ARCHIVE    │  compressed summaries + original chunks       │
│             │  moved to brain/archive/                      │
│             │  → only Treebeard reaches here                │
└─────────────────────────────────────────────────────────────┘
```

Transitions are silo-specific, not global. *"Current"* data goes stale in weeks; *"self"* data stays warm for years.

### Append-only with supersession

Updates never delete. Each chunk carries enough metadata to be replaced without being erased:

```json
{
  "id": "uuid",
  "created_at": "2026-05-17",
  "valid_from": "2026-05-17",
  "superseded_by": null,
  "domain": "self",
  "compression_eligible_after": "2027-05-17",
  "archived": false,
  "source": "brain/current/2026-05-17.md"
}
```

When a fact is updated, the new chunk is created and the old one's `superseded_by` field points to it. Default retrieval filters `superseded_by IS NULL`, so users see only the current truth. Treebeard, however, can follow the chain backward when asked historical questions. Cost is negligible — Qdrant stores this as plain payload, embeddings are not duplicated.

### Compression thresholds (tentative)

These thresholds are starting points, not commitments. S.M.E.A.G.O.L.'s logs will reveal whether they're too aggressive or too loose.

| Silo | Active window | Warm window | Compression strategy after warm |
|---|---|---|---|
| `kb_current` | 30 days | 60 days | Daily chunks → weekly summary → monthly summary |
| `kb_interests` | 90 days | 180 days | Group by topic, one summary per topic per quarter |
| `kb_conversations` | 180 days | 1 year | Keep summaries indefinitely, originals to cold storage |
| `kb_knowledge` | 180 days | 1 year | Deduplicate; only compress if topic recurs |
| `kb_projects` | 1 year | 2 years | Per-project rollup once project is marked closed |
| `kb_relations` | 1 year | 3 years | Cautious — relationships need long context windows |
| `kb_self` | 2 years | 5 years | Yearly snapshot ("who I was in 2024") |
| SQL (finances, dev-tracker) | never | never | Structured data is the value; transaction history doesn't compress |
| `brain/archive/` | n/a | n/a | Terminal tier; Treebeard is the only reader |

The principle behind these numbers: **the further from "stable facts about me", the more aggressive the compression**. Daily logs are noise after a month; identity is signal for a decade.

### Cost and growth — what to actually expect

Realistic projections for an active user (daily notes, weekly bank import, occasional reading):

| Component | Growth rate | After 1 year | Steady state (3+ years, post-Treebeard) |
|---|---|---|---|
| Vector DB (active) | ~0.5–1 MB/month | 10–15 MB | 30–50 MB (plateau) |
| SQL databases | ~1 MB/month | 15–30 MB | ~50 MB/year (linear) |
| Cold storage (raw files) | 50 MB – 1 GB/month | 5–20 GB | grows with reading habits |
| `brain/archive/` | starts year 2 | 0 | ~100 MB/year (compressed) |
| Smeagol logs | 10–40 MB/month | 100–500 MB | rotated, kept summaries only |

The headline number: **the active vector base plateaus**. Treebeard's compression ratio for noisy short-lived data (daily notes, captures) is roughly 50:1, which means linear ingest at the front turns into near-zero net growth at the back. Cold storage grows with how much you *read*, not how much the system stores about you — and cold storage is cheap.

CPU and RAM are not bottlenecks at this scale. A single chunk embed on RPi 5 is ~200 ms; a month's ingest totals seconds. Treebeard's nightly pass takes 2–5 minutes. Power draw for the whole Pi running 24/7 is ~6 W — meaning the entire system costs roughly **the price of a coffee per month in electricity**, regardless of how heavily it's used.

---

## 🛣️ Potential paths

These are illustrative use cases — directions the system could be developed toward. Not all will be built, and others will likely emerge.

- **Personal finance brain** — analyse bank and brokerage exports through G.I.M.L.I., cross-reference with current rates via L.E.G.O.L.A.S.
- **Developer self-knowledge** — combine `dev-tracker` data, project notes, and commit history to answer questions about my own work patterns and progress.
- **Homelab sentinel** — monitor Docker, Ollama, n8n, and other services; answer "why is X slow today?" type questions.
- **Job hunt assistant** — index job offers, CVs, and interview notes; surface alignment between offers and skill profile.
- **Learning companion** — track progress through self-written courses and technical books, identify gaps, suggest next topics.
- **Calendar & task management** — F.A.R.A.M.I.R. as a natural-language layer over calendar, reminders, and recurring tasks.
- **Development delegation** — F.A.R.A.M.I.R. forwards implementation tasks to [`agentic-sdlc-forge`](https://github.com/Jarkendar/agentic-sdlc-forge), turning conversation into actual code changes.
- **Knowledge gap detection** — S.M.E.A.G.O.L. surfaces patterns of failed queries, suggesting which silos or sources are missing.
- **Historical self-reflection** — T.R.E.E.B.E.A.R.D. answers questions like *"how have my interests shifted over the last two years?"* from compressed archives.
- **Proactive briefs** — F.A.R.A.M.I.R. delivers scheduled, system-initiated summaries and reminders on a configured channel — morning briefings, weekly retros, bill-due nudges — without waiting to be asked.
- **Reach-anywhere gateway** — converse with Gandalf from Telegram, Signal, email, or voice; one conversation thread that follows you across channels. Not just ingestion into `brain/` but a two-way dialogue interface.
- **Self-improving skills** — when a successful multi-agent workflow generalises, it gets captured as a skill and exported to `prompt-vault`; the fellowship's playbook grows from use rather than manual authoring.
- **Evolving self-model** — G.A.L.A.D.R.I.E.L. maintains a user profile that updates from accumulated context, not exclusively from manually maintained `core/profile.md`.

---

## 🌐 Ecosystem

G.A.N.D.A.L.F. does not stand alone — it sits inside a small constellation of personal projects, each with its own repository and lifecycle. The split is deliberate: each repo has one job, and the spine connecting them is plain files, git, n8n, and HTTP.

| Repo | Role in the system |
|---|---|
| **G.A.N.D.A.L.F.** *(this repo)* | The orchestrator and agent code. Reads `brain/`, queries other repos' data, delegates work. |
| **`brain/`** *(private)* | The knowledge base itself — markdown + selective SQLite. The thing Gandalf is *about*. |
| [`prompt-vault`](https://github.com/Jarkendar/prompt-vault) | Library of skills and prompts. Agents and skills are sourced from here; Gandalf references them by path. |
| [`dev-tracker`](https://github.com/Jarkendar/dev-tracker) | Structured-data source for G.I.M.L.I. — coding sessions, commits, time on task. |
| [`agentic-sdlc-forge`](https://github.com/Jarkendar/agentic-sdlc-forge) | External executor for development tasks. F.A.R.A.M.I.R. delegates here. |
| [`pi-automate`](https://github.com/Jarkendar/pi-automate) | Homelab infrastructure (Docker Compose, n8n flows, systemd units). The substrate everything else runs on, not a peer. |

How they're connected is intentionally low-tech: `brain/` and `prompt-vault` are read as files on disk, `dev-tracker` is read as SQLite, `agentic-sdlc-forge` is triggered over HTTP/n8n, and `pi-automate` hosts the whole thing in Docker. No service mesh, no shared schema, no orchestrator-of-orchestrators. A separate document (`ARCHITECTURE.md`, planned) will cover the on-disk layout, the workspace pattern, and how a meta-repo ties the constellation together.

---

## 🛠️ Tech stack

| Layer | MVP choice | Phase 2+ direction | Why |
|---|---|---|---|
| Orchestration runtime | Claude Code (skills + sub-agents) | Custom Python with LangGraph or LlamaIndex behind an engine abstraction | CC already implements the skill/agent split this project wants; rebuilding it from scratch in Python is later work. |
| Engine | Claude API via CC | Model-agnostic: Claude, local Ollama, hosted OSS | Privacy & cost tuning happens here, once shape is stable. |
| Local LLM runtime (Phase 2) | — | Ollama | ARM-friendly, model swapping, already in use. |
| Models (Phase 2, RPi 5) | — | Phi-3, Qwen2 7B, Gemma 3 | Small, capable, decent tool-calling. |
| Models (Phase 2, desktop fallback) | — | Larger Qwen / Llama via RTX 2070S | Heavy reasoning offloaded over Tailscale. |
| Knowledge store (text) | Markdown files in `brain/` git repo | + Qdrant index on top (built; the markdown stays canonical) | Files first, vectors when they earn it. |
| Knowledge store (structured) | SQLite | SQLite | Lightweight, file-based, plays well with git LFS or external mount. |
| Ingestion glue | n8n | n8n + webhooks | Already running on the homelab. |
| Background jobs | systemd timers | systemd timers | Already in use for `dev-tracker`. |
| Networking | Tailscale | Tailscale | Already in use for remote access. |
| Optional: voice | Whisper.cpp (STT) + Piper TTS | same | Lightweight enough for RPi 5. |

---

## 🚀 Running it

The MVP has no separate Gandalf binary — the project working directory is Gandalf's home, and `.claude/agents/gandalf.md` (the router, a main-thread agent) plus `CLAUDE.md` are what make Claude Code behave like one. `bin/gandalf` is a small launcher that removes the manual `cd` + repo-sync dance and starts the router; `gandalf --full` opens a full session instead (every tool, for `/init-brain`, `/ingest-conversation` and work outside the router's reach):

```bash
./bin/gandalf --install   # one-time: symlinks `gandalf` and `brain` into ~/.local/bin
gandalf                   # pulls this repo + brain/ on their current branch, then opens claude
brain -c                  # same thing — `brain` is just a second name for muscle memory
```

`gandalf` and `brain` are identical; pick whichever you reach for. Common flags:

| Flag | Effect |
|---|---|
| `-c` / `-r [id]` | continue or resume a previous Claude Code session (forwarded to `claude` as-is) |
| `--model <m>` / `--effort <lvl>` | forwarded to `claude` |
| `--yolo` | shorthand for `--dangerously-skip-permissions` |
| `--no-sync` | skip the git pull / branch check, start immediately |
| `--full` | open a full session instead of the router |

Before launching, the script pulls both this repo and `brain/` on their current branch, and asks before switching either one to `main` if it's elsewhere — uncommitted changes are never discarded.

---

## 🗺️ Roadmap

The MVP stage is done and the project is in the phase of growing the agent team around it. Status per step (details and dates in IMPLEMENTATION.md):

| # | Step | Status |
|---|---|---|
| 1 | **MVP — Gandalf on Claude Code, brain repo as markdown.** G.I.M.L.I. over SQLite, direct markdown access | done |
| 2 | **S.M.E.A.G.O.L.** — query logging | done |
| 3 | **S.A.M.W.I.S.E.** — semantic retrieval | done (Qdrant, index v2, reranker; usage review scheduled for 2026-11-30) |
| 4 | **F.A.R.A.M.I.R.** — calendar, reminders, delegation to `agentic-sdlc-forge` | calendar built, awaiting a live check; reminders and delegation open |
| 5 | **L.E.G.O.L.A.S.** — web search | built on `WebSearch` / `WebFetch`; search backend (SearXNG) open |
| 6 | **First skill (White Council)** | done and in use |
| 7 | **Ollama + engine abstraction** — the point where the system becomes local-first | open; the MVP privacy exception closes here |
| 8 | **Local models on the RPi 5** | open (the Pi already hosts the router, the index and the MCP servers; the engine is still the Claude API) |
| 9 | **B.I.L.B.O.** — indexing & vector DB | done, running on the Pi, reindexes on commit |
| 10 | **T.R.E.E.B.E.A.R.D.** — compression and archive retrieval | open; meaningful once 6–12 months of data accumulate |
| 11 | **Optional voice layer** | open — only if real usage proves it's wanted |

Beyond the numbered list, a team of domain agents grew from real use rather than from the original plan: records (Frodo, Balin, Círdan, Strider, Arwen), trainers and teachers, finance, and the Council's builders. Next candidates: reminders and delegation (Step 4), the conversational gateway (E1), and the engine abstraction (Step 7).

Order is a guess; Smeagol's logs will likely shuffle it.

---

*"All we have to decide is what to do with the time that is given us."* — Gandalf
