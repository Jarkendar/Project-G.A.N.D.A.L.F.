# G.I.M.L.I. — SQLite as MCP tools

The owner's SQLite databases, read-only, for the `gimli` sub-agent
(`.claude/agents/gimli.md`). It replaces the agent's former `Bash` +
`sqlite3 -readonly`: the agent now holds three tools and no shell, and
"read-only" is enforced here instead of promised in a prompt.

## Tools

| Tool | What it returns |
|---|---|
| `databases()` | Every database in the registry: alias, file, privacy, owner, tables |
| `schema(database, table?)` | The CREATE statements of a database or one table |
| `query(database, sql, limit?)` | One SELECT as a markdown table (200 rows by default, 1000 at most) |

## Registry

`$BRAIN_PATH/db/*.db` ∪ `GIMLI_EXTRA_DBS`, both read from
`.claude/gandalf.env` on every call (no restart after adding a database). A
path in `GIMLI_EXTRA_DBS` that does not exist is reported as a note, not an
error. `smeagol.db` is never listed.

Privacy and owner come from the table in `brain/db/CLAUDE.md` and head every
result. A database missing from that table is labelled PRIVATE — add a row
there when a database is introduced. The server only labels; whether a
PRIVATE result may be shown is the agent's rule.

## How read-only is enforced

1. Each database is opened with `mode=ro` and `PRAGMA query_only`.
2. An SQLite authorizer allows SELECT, reads, functions, recursive CTEs and
   the schema-reading PRAGMAs (`table_info`, `index_list`, …) — everything
   else is denied, including ATTACH, so no file outside the registry can be
   reached.
3. One statement per call; a query is interrupted after 20 s.

In a query on one database the others are attached under their alias
(`SELECT … FROM dev_tracker.sessions`), up to SQLite's limit of 10.

## Setup

```bash
python3 -m venv .claude/scripts/gimli/.venv
.claude/scripts/gimli/.venv/bin/pip install -r .claude/scripts/gimli/requirements.txt
```

Registered as `gimli` in `.mcp.json` (stdio); the three tools are pre-allowed
in `.claude/settings.json`. Its own venv holds the MCP SDK only — SQLite
comes with Python, and the `sqlite3` command-line tool is not needed.
