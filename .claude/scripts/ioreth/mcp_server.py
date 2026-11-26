#!/usr/bin/env python3
# I.O.R.E.T.H. — Interpretation Of Results, Evolution & Trends in Health.
#
# The lab results store (labs.py) as MCP tools, so the Ioreth sub-agent needs
# no shell and no SQL: `preview` and `save` of one examination, and the fixed
# reads of its own database — `reports`, `history`, `compare`. Ad hoc analysis
# of labs.db stays with G.I.M.L.I.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import sqlite3

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

import labs

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)

server = MCPServer(
    name="ioreth",
    log_level="WARNING",
    instructions=(
        "The owner's lab results: saves one examination (transcription file and database rows) "
        "and reads its history. It belongs to the I.O.R.E.T.H. sub-agent — hand lab results to "
        "it rather than calling these tools yourself. The data is PRIVATE."
    ),
)


def _run(function, *args) -> str:
    try:
        return function(labs.brain_path(), *args)
    except (labs.Refused, ValueError, TypeError, AttributeError, OSError, sqlite3.Error) as exc:
        return f"IORETH: refused — {exc}"


@server.tool(annotations=READ)
def preview(report: dict) -> str:
    """Check one examination and return the transcription file as `save` would
    write it, the warnings and a `digest`. Writes nothing.

    `report` fields — exam_date (YYYY-MM-DD, required), result_date, provider,
    collection_point, identifiers ([{label, value}]: order / exam / document
    numbers, labelled as printed), results ([{material, param, name, value,
    unit, ref, flag, uncertain}]: name, value, unit, ref and flag exactly as
    printed; param is one stable key per test, reused across labs), text (all
    other content of the document), attachments (file names), pages_read,
    supersedes (id of the report this one corrects). Never PESEL, the address
    or anything else identifying the owner."""
    return _run(labs.preview, report)


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False))
def save(report: dict, digest: str) -> str:
    """Save one examination the owner approved: the transcription file and the
    rows in db/labs.db, both or neither. `report` and `digest` must be those of
    the `preview` the owner saw. Returns the paths for the commit."""
    return _run(labs.save, report, digest)


@server.tool(annotations=READ)
def reports() -> str:
    """Every saved examination: id, dates, source (provider and numbers), kind,
    number of results and the transcription's path in brain/."""
    return _run(labs.list_reports)


@server.tool(annotations=READ)
def history(param: str = "") -> str:
    """Without `param`: the parameter keys stored, with unit and count. With one:
    every value over time, each with the range of its own printout, the status
    computed against it and the source."""
    return _run(labs.history, param)


@server.tool(annotations=READ)
def compare(report_id: int = 0) -> str:
    """One examination (0 = the latest tabular one), each result with its status
    (below / above / within / unknown) and the change against the previous value
    of the same parameter. Different units are not compared."""
    return _run(labs.compare, report_id)


if __name__ == "__main__":
    server.run("stdio")
