#!/usr/bin/env python3
# G.I.M.L.I. — Generative Intelligence Mining Local Information.
#
# The owner's SQLite databases as MCP tools — read-only by construction, so
# the Gimli sub-agent needs no shell:
#   - every database is opened `mode=ro` with `query_only` on;
#   - an authorizer lets through SELECT and the schema-reading PRAGMAs and
#     nothing else — no writes, no ATTACH of a file outside the registry;
#   - one statement per call, a row limit and a time limit.
#
# Registry: $BRAIN_PATH/db/*.db ∪ GIMLI_EXTRA_DBS (both from
# .claude/gandalf.env). Privacy and owner of each database come from the table
# in brain/db/CLAUDE.md and are printed with every result; a database missing
# from that table is treated as PRIVATE. The server labels, it does not judge:
# what may be shown is the agent's rule (.claude/agents/gimli.md).
#
# Tools: databases, schema, query.
#
# Run by Claude Code from .mcp.json (stdio).

import os
import re
import sqlite3
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]

NEVER = {"smeagol.db"}  # Smeagol's own log store — not Gimli's to read
MAX_ROWS = 1000
MAX_CELL = 200
TIME_LIMIT_S = 20
ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}
READ_PRAGMAS = {"table_info", "table_xinfo", "index_list", "index_info", "foreign_key_list"}

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

server = MCPServer(
    name="gimli",
    log_level="WARNING",
    instructions=(
        "The owner's SQLite databases (brain/db/ and GIMLI_EXTRA_DBS), read-only. Analytical "
        "SQL over them belongs to the G.I.M.L.I. sub-agent — route quantitative questions to "
        "it rather than calling these tools yourself. Every result is labelled with the "
        "database's privacy level."
    ),
)


# --- registry ---------------------------------------------------------------------

def read_gandalf_env(project_dir: Path) -> dict:
    """KEY=VALUE pairs from .claude/gandalf.env, taken literally (no shell quoting)."""
    values = {}
    try:
        for line in (project_dir / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def _resolve(raw: str) -> Path:
    path = Path(os.path.expanduser(raw))
    return path if path.is_absolute() else (PROJECT_DIR / path).resolve()


def _labels(brain: Path | None) -> dict:
    """{file name: (privacy, owner)} from the table in brain/db/CLAUDE.md."""
    labels = {}
    if brain:
        try:
            text = (brain / "db" / "CLAUDE.md").read_text()
        except OSError:
            text = ""
        for name, privacy, owner in re.findall(
            r"^\|\s*`([^`|]+\.db)`\s*\|\s*(PUBLIC|PRIVATE)\s*\|\s*([^|]*)\|", text, re.M
        ):
            labels[name] = (privacy, owner.replace("`", "").strip())
    return labels


def _registry() -> tuple[dict, list[str]]:
    """({alias: {path, file, privacy, owner}}, notes about what was left out)."""
    env = read_gandalf_env(PROJECT_DIR)
    raw_brain = os.environ.get("BRAIN_PATH") or env.get("BRAIN_PATH")
    brain = _resolve(raw_brain) if raw_brain else None
    paths = sorted((brain / "db").glob("*.db")) if brain and (brain / "db").is_dir() else []
    extra = os.environ.get("GIMLI_EXTRA_DBS") or env.get("GIMLI_EXTRA_DBS") or ""
    paths += [_resolve(p.strip()) for p in extra.split(",") if p.strip()]

    labels, registry, notes = _labels(brain), {}, []
    if not brain:
        notes.append("BRAIN_PATH is not set in .claude/gandalf.env — only GIMLI_EXTRA_DBS is listed")
    for path in paths:
        if path.name in NEVER:
            continue
        if not path.is_file():
            notes.append(f"{path.name}: listed in GIMLI_EXTRA_DBS but not found at {path}")
            continue
        alias = re.sub(r"\W", "_", path.stem)
        if alias in registry:
            notes.append(f"{path}: skipped, another database is already called `{alias}`")
            continue
        privacy, owner = labels.get(path.name, ("PRIVATE", "unlisted — add it to brain/db/CLAUDE.md"))
        registry[alias] = {"path": path, "file": path.name, "privacy": privacy, "owner": owner}
    return registry, notes


def _authorize(action, arg1, *_):
    if action in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_PRAGMA and arg1 in READ_PRAGMAS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _open(registry: dict, alias: str) -> sqlite3.Connection:
    """`alias` as the main database, the rest of the registry attached under
    their aliases (SQLite attaches 10 at most), then locked to SELECT."""
    conn = sqlite3.connect(f"file:{registry[alias]['path']}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    for other in [a for a in registry if a != alias][:9]:
        conn.execute(f"ATTACH DATABASE ? AS [{other}]", (f"file:{registry[other]['path']}?mode=ro",))
    conn.set_authorizer(_authorize)
    deadline = time.monotonic() + TIME_LIMIT_S
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    return conn


def _pick(registry: dict, database: str) -> str | None:
    """The alias for a name given as `fitness`, `fitness.db` or a path."""
    wanted = re.sub(r"\W", "_", Path(database).stem)
    return wanted if wanted in registry else None


def _label(entry: dict) -> str:
    return f"{entry['file']} — {entry['privacy']} (owner: {entry['owner']})"


def _unknown(registry: dict, database: str) -> str:
    return f"GIMLI: no database `{database}`. Available: {', '.join(registry) or 'none'}"


def _cell(value) -> str:
    if value is None:
        return ""
    text = f"<{len(value)} bytes>" if isinstance(value, bytes) else str(value)
    text = text.replace("|", "\\|").replace("\n", " ")
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 1] + "…"


# --- tools ------------------------------------------------------------------------

@server.tool(annotations=READ)
def databases() -> str:
    """Every database Gimli can read: alias, file, privacy level, owner and tables.
    Call it first. In a query on one database the others are attached under their
    alias, e.g. `SELECT … FROM dev_tracker.sessions`."""
    registry, notes = _registry()
    lines = []
    for alias, entry in registry.items():
        try:
            conn = _open(registry, alias)
            try:
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM main.sqlite_master WHERE type IN ('table', 'view') "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )]
            finally:
                conn.close()
            lines.append(f"{alias}: {_label(entry)}\n  tables: {', '.join(tables) or 'none'}")
        except sqlite3.Error as err:
            lines.append(f"{alias}: {_label(entry)}\n  unreadable: {err}")
    if not lines:
        lines.append("GIMLI: no databases in the registry")
    return "\n".join(lines + [f"note: {n}" for n in notes])


@server.tool(annotations=READ)
def schema(database: str, table: str = "") -> str:
    """The CREATE statements of one database (alias from `databases`) — all tables,
    views and indexes, or only those of `table`."""
    registry, _ = _registry()
    alias = _pick(registry, database)
    if not alias:
        return _unknown(registry, database)
    conn = _open(registry, alias)
    try:
        rows = conn.execute(
            "SELECT sql FROM main.sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "AND (?1 = '' OR tbl_name = ?1) ORDER BY type DESC, name",
            (table,),
        ).fetchall()
    except sqlite3.Error as err:
        return f"GIMLI: {err}"
    finally:
        conn.close()
    if not rows:
        return f"GIMLI: no table `{table}` in {alias}" if table else f"GIMLI: {alias} is empty"
    return f"{_label(registry[alias])}\n\n" + ";\n\n".join(r[0] for r in rows) + ";"


@server.tool(annotations=READ)
def query(database: str, sql: str, limit: int = 200) -> str:
    """Run one SELECT (or WITH … SELECT) on a database (alias from `databases`) and
    return a markdown table. Anything that is not a read is refused. At most `limit`
    rows come back (up to 1000) — aggregate in SQL rather than fetching raw rows."""
    registry, _ = _registry()
    alias = _pick(registry, database)
    if not alias:
        return _unknown(registry, database)
    limit = max(1, min(limit, MAX_ROWS))
    conn = _open(registry, alias)
    try:
        cursor = conn.execute(sql)
        if cursor.description is None:
            return "GIMLI: not a query — only SELECT is allowed"
        columns = [c[0] for c in cursor.description]
        rows = cursor.fetchmany(limit + 1)
    except sqlite3.OperationalError as err:
        hint = f" (over {TIME_LIMIT_S}s — narrow the query)" if "interrupt" in str(err) else ""
        return f"GIMLI: {err}{hint}"
    except (sqlite3.Error, sqlite3.Warning) as err:
        refused = " — read-only: only SELECT is allowed" if "authoriz" in str(err) else ""
        return f"GIMLI: {err}{refused}"
    finally:
        conn.close()
    more = len(rows) > limit
    rows = rows[:limit]
    head = f"{_label(registry[alias])}\n{len(rows)} row(s)" + (
        f" — more exist, only the first {limit} shown" if more else ""
    )
    if not rows:
        return head
    table = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    table += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return head + "\n\n" + "\n".join(table)


if __name__ == "__main__":
    server.run("stdio")
