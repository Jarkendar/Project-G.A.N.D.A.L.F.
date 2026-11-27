# I.O.R.E.T.H. — the lab results store

The MCP server of the `ioreth` sub-agent (`.claude/agents/ioreth.md`). The
logic is in `labs.py` (standard library), the tools in `mcp_server.py`.

| Tool | What it does |
|---|---|
| `preview(report)` | checks one examination; returns the file as it would be written, warnings and a digest. Writes nothing |
| `save(report, digest)` | writes the transcription and the rows, both or neither; refuses a report that differs from the previewed one |
| `reports()` | the saved examinations, with source and transcription path |
| `history(param?)` | the stored parameter keys, or one parameter over time |
| `compare(report_id?)` | one examination against the previous values |

Where it goes:

- `brain/core/health/labs/reports/<exam date>_<provider>.md` — the
  transcription: source (provider, collection point, order and exam numbers,
  dates), the results as printed, the rest of the document's text;
- `brain/db/labs.db` — tables `reports` (source, path to the transcription,
  `superseded_by`) and `results`. This server is its only writer; the three
  reads are the owner's fixed reads, ad hoc questions are G.I.M.L.I.'s.

Rules held by the code:

- originals (PDF, images) are never opened, copied or stored;
- numbers, ranges, status and change are computed from the printed strings; a
  range that is not a single plain one is not judged, different units are not
  compared;
- the same date, provider and results are refused as a duplicate;
- nothing is deleted: a correction names the old report in `supersedes`;
- an identifier labelled PESEL, or a PESEL-shaped number in the text, is
  refused.

Test: `python3 .claude/scripts/ioreth/test_labs.py`. `BRAIN_PATH` comes from
`.claude/gandalf.env` on every call.
