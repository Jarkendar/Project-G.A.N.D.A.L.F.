# F.R.O.D.O. — the fitness upsert, as an MCP tool

One tool for the `frodo` sub-agent (`.claude/agents/frodo.md`), which
processes the daily note without a shell.

| Tool | What it does |
|---|---|
| `fitness_upsert(strava_id, date, sport_type, …)` | `INSERT OR REPLACE` of one Strava activity into `brain/db/fitness.db`, keyed on `strava_id` |

No SQL comes in — only the named fields of one row, bound as parameters. A
field left out is stored as NULL; `synced_at` is set by the server; the table
is created on first use with the schema the `/daily` skill documents. It
refuses a non-positive id, a date that is not a real `YYYY-MM-DD`, an empty
sport type and negative numbers.

`data_providers/strava_sync.py` (the owner's batch sync) writes the same
table; reading and analysing it is G.I.M.L.I.'s.

`BRAIN_PATH` comes from `.claude/gandalf.env` on every call. Started by
Claude Code from `.mcp.json` over stdio, on the Gimli server's venv.
