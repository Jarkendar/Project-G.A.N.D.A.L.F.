# E.L.R.O.N.D. — the Council's record, as an MCP tool

One tool for the `elrond` sub-agent (`.claude/agents/elrond.md`), which
writes the synthesis of a White Council.

| Tool | What it does |
|---|---|
| `record(council_dir, slug, title, question, voices, tags, consensus)` | assembles the record from the Council's working folder and writes `brain/knowledge/councils/<today>_<slug>.md` |

The synthesis and every voice's answer are **copied** from the folder
(`synthesis.md`, `blind-<voice>.md`, `critique-<voice>.md`,
`critique2-<voice>.md`, `question.md`) — nobody retypes a 60k-character
record. The frontmatter follows `knowledge/councils/CLAUDE.md`; `privacy` is
always `private`; the number of critique rounds is counted from the files.

It refuses: a folder outside the temp directory, a voice with no answer
file, a file that belongs to no listed voice, a bad slug or tag, and an
existing record (records are never overwritten).

`BRAIN_PATH` comes from `.claude/gandalf.env` on every call. Started by
Claude Code from `.mcp.json` over stdio, on the Gimli server's venv.
