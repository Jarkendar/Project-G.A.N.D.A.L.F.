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
| "what do I know about", "my goals", "tell me about", "notes on", "context on", open-ended personal knowledge | → **brain/ markdown** (direct read) |
| Ambiguous — could be both | Prefer markdown for qualitative, SQL for quantitative; if genuinely ambiguous, split: run both and merge. |

Do not route to G.I.M.L.I. if no SQLite databases are available (registry empty).
Do not route to brain/ markdown if BRAIN_PATH is not resolved.

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

## Step 2b — route to brain/ markdown (knowledge query)

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

## Step 3 — synthesise

Compose the final answer from the agent result or the markdown content:
- Be concise and direct.
- If the answer came from Gimli: include the key numbers and the source database.
- If the answer came from markdown: summarise what was found and cite the file path(s).
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
- Gandalf does not spin up new agents beyond Gimli in Step 1.
  Samwise (semantic search) is Step 3 of the roadmap — not yet.

---

## Roadmap note

This is the **Step 1 MVP** implementation of Gandalf (router + Gimli + direct
markdown read). Planned additions:
- **Step 3:** S.A.M.W.I.S.E. replaces direct grep for unstructured queries.
- **Step 4:** F.A.R.A.M.I.R. added as a route for calendar/delegation queries.
- **Step 5:** L.E.G.O.L.A.S. added as a route for web-search queries.
