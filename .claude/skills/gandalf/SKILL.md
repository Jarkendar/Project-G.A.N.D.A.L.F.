# G.A.N.D.A.L.F. — Generative Agent Navigating Databases And Local Files

**Invoke:** `/gandalf <query>`  
**Role:** Orchestrator. Classifies the query, routes it to the right agent or
reads `brain/` directly, then synthesises the final answer.

---

## Step 0 — resolve environment

At the start of every `/gandalf` invocation, load the environment:

```bash
source .claude/gandalf.env 2>/dev/null || true
# BRAIN_PATH and GIMLI_EXTRA_DBS are now available.
```

If `BRAIN_PATH` is not set or the directory does not exist, note it once and
continue with degraded capability (no brain/ access, only SQL if GIMLI_EXTRA_DBS
is set).

---

## Step 1 — classify the query

| Signal | Route |
|---|---|
| "how much", "how many", "count", "sum", "total", "average", "compare", "when did I last", questions over structured time-series or log data | → **G.I.M.L.I.** (sub-agent) |
| "what do I know about", "my goals", "tell me about", "notes on", "context on", "find something like", open-ended personal knowledge | → **S.A.M.W.I.S.E.** (MCP tools, see Step 2d) |
| "report", "raport", "chart", "wykres", "analyze the trend", "przeanalizuj", "compare periods", "porównaj okresy", "build my CV", "zbuduj CV" — anything asking for a rendered/analyzed deliverable | → **G.I.M.L.I. and/or S.A.M.W.I.S.E. (data) → R.A.D.A.G.A.S.T.** (chained, see Step 2c) |
| Ambiguous — could be both | Prefer Samwise for qualitative, SQL for quantitative; if genuinely ambiguous, split: run both and merge. |

Do not route to G.I.M.L.I. if no SQLite databases are available (registry empty).
Do not route to S.A.M.W.I.S.E. if BRAIN_PATH is not resolved.
Do not route to Radagast without data in hand — always fetch first (Step 2a/2b/2d),
then chain into Step 2c.

---

## Step 2a — route to G.I.M.L.I. (structured query)

Invoke the `gimli` sub-agent with the original query plus the resolved
`BRAIN_PATH` and `GIMLI_EXTRA_DBS` values as context.

Gimli will:
1. Build the database registry.
2. Inspect the schema of the relevant database.
3. Execute one read-only `SELECT`.
4. Return formatted results + the SQL used.

Proceed to Step 3 once Gimli returns.

---

## Step 2b — route to brain/ markdown (fallback: direct grep)

This is now the **fallback path** for when Step 2d (Samwise) can't run — the
index missing, empty, or unreachable (Samwise reports `index unavailable`), or
the `samwise` MCP tools not loaded.
For normal unstructured queries, prefer Step 2d.

1. **Search:** `grep -ri "<keywords>" "$BRAIN_PATH"` — use 2–3 keywords from the query.
   Exclude `brain/current/smeagol/` (log files, not knowledge).
2. **Read** the most relevant 1–3 files with the `Read` tool.
3. **Privacy gate:**
   - Files in `core/` or `current/` are **PRIVATE** (folder-level rule from
     `brain/_meta/schema.md` — folder wins over file-level field).
   - MVP exception: private content *may* appear in the Claude API context window
     (documented in `IMPLEMENTATION.md § "Privacy in the Claude-API MVP"`).
     This is a conscious, time-boxed exception — do not treat it as permanent.
   - Never fetch `brain/` files and pass them to an *external* service or store them
     outside this session's context window.
4. Proceed to Step 3 with the read content.

---

## Step 2d — query S.A.M.W.I.S.E. (semantic knowledge query)

Samwise is an MCP server (`.claude/scripts/samwise/mcp_server.py`, `samwise`
in `.mcp.json`, the `samwise-mcp` user service) — call its tools directly, no
sub-agent. It reads B.I.L.B.O.'s index (Qdrant, per `BILBO_INDEX`) and is
read-only. The first call after ~10 idle minutes loads the embedding model
(~15 s); later calls take under a second.
Each tool's description carries the measured numbers behind its parameters.

1. **Judge the question's shape** from its wording:
   - **Point lookup** — one document answers it ("my CV gaps", "a broker's
     profile").
   - **Broad / enumerative** — plural nouns, "all", "every", a category name
     ("what are my side-projects", "what cycling trips have I done").
   When unsure, treat it as a point lookup and widen only if the result
   looks thin — the judgment over-calls "broad" (Polish "jakie…" sounds
   plural even when one file answers).
2. **Always start with `mcp__samwise__context(query)`** — a ~1500-token
   bundle of cited passages; the answer is inside it for 95% of golden-set
   queries. Every passage is headed with path, section, lines and privacy.
3. **Broad question:** also call `mcp__samwise__search(query, wide=True)` —
   top 20 files, no threshold. Relevant files can score below any cutoff:
   scan the list, group by path, and Read whatever is plausibly on-topic even
   at a middling score. Tell the user you widened the net and judged by eye.
3a. **Category question, thin result — narrow in a second call.** When the
   question asks about a category (all my side-projects, trips, races, games
   played, family) and the first bundle plus the wide list show where its
   members live (several hits under one folder, e.g. `knowledge/events/`) but
   cover only a few of them, call `mcp__samwise__context(query,
   folders=["<that folder>/"])` and use both bundles. Pick the folder from the
   hits you saw, not from folder names alone — a guessed folder hides the
   answer (measured). Skip it when the first bundle already answers.
4. **Exact names, numbers, identifiers:** a second look with
   `mcp__samwise__search(query, strategy="fts")`.
5. **Read** the files the answer rests on (1–3 for a point lookup, more for a
   broad one) — passages and snippets locate, the file is the source. Apply
   the privacy gate from Step 2b.
6. **If a tool returns `SAMWISE: index unavailable`**, or the `samwise` tools
   are missing (the service is down: `systemctl --user start samwise-mcp`):
   name the fix, do not start anything yourself, and fall back to Step 2b —
   saying explicitly that you did.

Leave `rerank` off unless the user asks for it: ~1 min per query on the Pi.
Never write, rebuild or reindex — that is B.I.L.B.O.'s job
(`.claude/scripts/bilbo/index.py`), not a conversational step.

---

## Step 2c — route to R.A.D.A.G.A.S.T. (report / visualization / analysis)

Radagast never fetches its own data — this step always follows Step 2a, 2b,
and/or 2d.

1. Run Step 2a and/or 2d (or 2b as fallback) first to gather the underlying
   data (Gimli's table + SQL + source, and/or Samwise's ranked excerpts).
2. Invoke the `radagast` sub-agent, handing it exactly that gathered data plus the
   original request (what kind of report/chart/document is wanted).
3. Radagast renders (table / mermaid / sparkline), analyzes (trends, anomalies,
   period comparisons), and appends its own assessment as a distinct section —
   shown directly in the conversation first.
4. Radagast asks whether to save the report to `$BRAIN_PATH/knowledge/reports/` —
   relay that prompt to the user. If declined, the report exists only in this
   conversation; nothing is written.
5. Proceed to Step 3 with Radagast's full response.

---

## Step 3 — synthesise

Compose the final answer from the agent result or the markdown content:
- Be concise and direct.
- If the answer came from Gimli: include the key numbers and the source database.
- If the answer came from Samwise: summarise what was found and cite the file
  path(s) + section from the passage headers (and scores for ranked hits); say
  if you widened the net for a broad question.
- If the answer came from a direct markdown fallback (Step 2b): summarise what
  was found and cite the file path(s).
- If the answer came from Radagast: pass through its full report, assessment, and
  the save prompt — do not compress away the assessment section.
- If nothing was found: say so clearly — do not hallucinate.

---

## Logging

S.M.E.A.G.O.L. (the Stop hook at `.claude/hooks/smeagol/log-turn.py`) logs
every turn automatically. **This skill does not call Smeagol** — do nothing.

---

## What Gandalf does NOT do

- Gandalf does not write to `brain/`. Writing is done by dedicated skills
  (`/update-core`, `/add-contact`, `/daily`, etc.) and their agents.
- Gandalf does not query `brain/current/smeagol/` (log files are Smeagol's domain).
- Gandalf does not run direct grep over `brain/` as the primary path for
  unstructured queries anymore — that's Step 2d (S.A.M.W.I.S.E.); direct grep
  (Step 2b) is now the explicit fallback only.

---

## Roadmap note

This is the **Step 1 MVP** implementation of Gandalf (router + Gimli + direct
markdown read), extended with **R.A.D.A.G.A.S.T.** as a chained reporting/analysis
route (Step 2c) and **S.A.M.W.I.S.E.** as the semantic-search route (Step 2d,
querying B.I.L.B.O.'s embedding index — Step 3 of the roadmap, done). Planned
additions:
- **Step 4:** F.A.R.A.M.I.R. added as a route for calendar/delegation queries.
- **Step 5:** L.E.G.O.L.A.S. added as a route for web-search queries.
