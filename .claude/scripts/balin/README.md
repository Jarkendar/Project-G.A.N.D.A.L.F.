# B.A.L.I.N. — the archive of an English review's transcripts

One tool for the `balin` sub-agent (`.claude/agents/balin.md`), which has no
shell to hash a transcript or to copy it unchanged.

| Tool | What it does |
|---|---|
| `archive_transcripts(items, now, dry_run=false)` | writes each transcript as a new file in `brain/conversations/`, the way `/ingest-conversation` stores a dropped one |

`items` is a list (at most 10) of `{title, summary, tags, transcript}`. Per item
the tool:

- names the file `YYYY-MM-DDTHH-MM-SS_agent_<slug>.md` — item *N* gets `now` + *N−1*
  seconds, so several transcripts of one session are separate files;
- writes the frontmatter of `brain/conversations/CLAUDE.md` with `source: agent`,
  `privacy: private`, the assistant detected from the `Claude: ` / `Gemini: `
  lines (a tie is `unknown`), the tags given plus `english-review` and the
  assistant, and `content_hash: sha256:<hex>` of the transcript as given;
- writes `## Summary`, then `## Transcript` — the text unchanged; the file is
  read back and compared;
- skips a transcript already archived (same `content_hash` in any file of
  `conversations/`, also one made by `/ingest-conversation`; a difference in
  the trailing newline is tolerated) and one repeated in the same call.

It never overwrites, never creates `conversations/`, touches nothing outside it,
and is whole-or-nothing: what one call created is removed again if a later write
of the same call fails. `dry_run` writes nothing and returns the file names and
the duplicates, for the plan.

The logic is `archive.py` (stdlib); `mcp_server.py` is the wrapper (the Gimli
venv, as for Thorin).

```
python3 .claude/scripts/balin/test_archive.py
python3 .claude/scripts/balin/test_mcp_server.py
```
