# T.H.O.R.I.N. — what the finance agents would need a shell for, as MCP tools

Three tools: two for the `thorin` sub-agent (`.claude/agents/thorin.md`),
which runs `/ingest-finance` without a shell, and one for `gloin`
(`.claude/agents/gloin.md`), which fetches the company reports for him.

| Tool | Used by | What it does |
|---|---|---|
| `read_export(filename="")` | thorin | without a name: the myFund exports waiting in `brain/current/inbox/`; with one: the net position per ticker computed from that XML export. Reads only |
| `archive_export(filename)` | thorin | writes the readable `.md` copy of an XML export into `current/inbox/_processed/` and moves the source file there |
| `edgar_reports(ticker, since)` | gloin | the 10-K / 10-Q filings of one US ticker filed since a date, with the key figures, from SEC EDGAR |

`read_export` does the arithmetic of `/ingest-finance` step 3 — signed
quantities summed per ticker, open above 0.001 units — so no model adds up
transactions. The average of an open position is the cost of the lots still
held (oldest sold first, or the lot a sale names; commission included, as
myFund does), so a position closed and opened anew starts its average afresh;
a closed position shows the average over all its buys. A spin-off (`SPINOFF=1`)
is flagged in the notes, not allocated: the export does not name the parent
whose cost myFund lowers, so the agent asks the owner. Checked 2026-10-13
against the owner's figures on the IKE, IKZE and XTB exports. It was checked against the four exports
converted by hand in 2026-06: every open position identical. The XML itself
never enters an agent's context.

Both export tools take a plain file name in the inbox — nothing with a folder
in it, and only a name holding `myfund` or `portfel`, so no other inbox file
can be read or moved through them. `archive_export` refuses when `_processed/` already holds a file of that name. It is
the only way either agent changes `current/inbox/`.

`edgar_reports` exists because SEC EDGAR refuses requests without a
descriptive `User-Agent`, which `WebFetch` cannot set, and because
`companyfacts` JSON runs to megabytes. It returns, per filing, the report file
name (`YYYY-QQ.md` / `YYYY-annual.md`, by period end) and each figure in a
short form with the exact value and the period it covers. For a 10-Q it takes
the single-quarter figure and marks a year-to-date one as such; a filing
whose figures EDGAR has not published yet is marked `NO FIGURES YET`.

`SEC_USER_AGENT` in `.claude/gandalf.env` should hold a name and a contact
address, as SEC asks. With it, a ticker is resolved against SEC's full ticker
list and only the company's CIK is requested; without it, the lookup goes
through EDGAR's full-text search and the ticker itself is sent.

`BRAIN_PATH` comes from `.claude/gandalf.env` on every call. Started by Claude
Code from `.mcp.json` over stdio, on the Gimli server's venv.
