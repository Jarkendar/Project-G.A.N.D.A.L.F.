# F.R.O.D.O. — what Frodo would need a shell for, as MCP tools

Two tools for the `frodo` sub-agent (`.claude/agents/frodo.md`), which files
the owner's records into brain/ without a shell.

| Tool | What it does |
|---|---|
| `fitness_upsert(strava_id, date, sport_type, …)` | `INSERT OR REPLACE` of one Strava activity into `brain/db/fitness.db`, keyed on `strava_id` |
| `now()` | the local date and time — `iso` for frontmatter, `file` for timestamped file names |

`fitness_upsert`: no SQL comes in — only the named fields of one row, bound as parameters. A
field left out is stored as NULL; `synced_at` is set by the server; the table
is created on first use with the schema the `/daily` skill documents. It
refuses a non-positive id, a date that is not a real `YYYY-MM-DD`, an empty
sport type and negative numbers.

`data_providers/strava_sync.py` (the owner's batch sync) writes the same
table; reading and analysing it is G.I.M.L.I.'s.

`BRAIN_PATH` comes from `.claude/gandalf.env` on every call. Started by
Claude Code from `.mcp.json` over stdio, on the Gimli server's venv.
