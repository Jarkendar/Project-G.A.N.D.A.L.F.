#!/usr/bin/env python3
# F.R.O.D.O. — Filing Records Of Days & Observations.
#
# The two things the Frodo sub-agent would otherwise need a shell for, as MCP
# tools:
#
#   fitness_upsert  the one database write the daily note needs — one Strava
#                   activity into brain/db/fitness.db (INSERT OR REPLACE keyed
#                   on strava_id, the statement the /daily skill documents).
#                   No SQL comes in, only the named fields of one row.
#   now             the local date and time, for `date:` fields and
#                   timestamped file names — an agent has no clock.
#
# Reading and analysing fitness.db stays with G.I.M.L.I.
#
# Run by Claude Code from .mcp.json (stdio), with the Gimli server's venv —
# the MCP SDK is its only dependency.

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

PROJECT_DIR = Path(__file__).resolve().parents[3]

SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
    strava_id       INTEGER PRIMARY KEY,
    date            TEXT    NOT NULL,
    sport_type      TEXT    NOT NULL,
    name            TEXT,
    distance_m      REAL,
    moving_time_s   INTEGER,
    elapsed_time_s  INTEGER,
    elevation_m     REAL,
    average_hr      INTEGER,
    max_hr          INTEGER,
    average_cadence REAL,
    average_speed   REAL,
    average_watts   REAL,
    calories        INTEGER,
    suffer_score    INTEGER,
    kilojoules      REAL,
    workout_type    INTEGER,
    synced_at       TEXT    NOT NULL
)
"""
COLUMNS = (
    "strava_id", "date", "sport_type", "name", "distance_m", "moving_time_s",
    "elapsed_time_s", "elevation_m", "average_hr", "max_hr", "average_cadence",
    "average_speed", "average_watts", "calories", "suffer_score", "kilojoules",
    "workout_type", "synced_at",
)

server = MCPServer(
    name="frodo",
    log_level="WARNING",
    instructions=(
        "Writes one Strava activity into the owner's fitness database, and tells the local "
        "time. It belongs to the F.R.O.D.O. sub-agent, which files the owner's records into "
        "brain/ — hand the note to it rather than calling these tools yourself. Questions "
        "about fitness data go to G.I.M.L.I."
    ),
)


def _fitness_db() -> Path:
    raw = ""
    try:
        for line in (PROJECT_DIR / ".claude" / "gandalf.env").read_text().splitlines():
            line = line.strip()
            if line.startswith("BRAIN_PATH="):
                raw = line.partition("=")[2].strip().strip("\"'")
    except OSError:
        pass
    brain = Path(os.path.expanduser(raw or "../brain"))
    brain = (brain if brain.is_absolute() else PROJECT_DIR / brain).resolve()
    if not (brain / "db").is_dir():
        raise ValueError(f"{brain}/db does not exist — BRAIN_PATH wrong or brain/ not initialised")
    return brain / "db" / "fitness.db"


@server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def fitness_upsert(
    strava_id: int,
    date: str,
    sport_type: str,
    name: str | None = None,
    distance_m: float | None = None,
    moving_time_s: int | None = None,
    elapsed_time_s: int | None = None,
    elevation_m: float | None = None,
    average_hr: int | None = None,
    max_hr: int | None = None,
    average_cadence: float | None = None,
    average_speed: float | None = None,
    average_watts: float | None = None,
    calories: int | None = None,
    suffer_score: int | None = None,
    kilojoules: float | None = None,
    workout_type: int | None = None,
) -> str:
    """Insert or replace one Strava activity in brain/db/fitness.db, keyed on
    `strava_id` (running it again for the same activity overwrites the row, never
    duplicates it). `date` is the activity's start day, YYYY-MM-DD. Take every value
    from Strava's `get-activity-details`; leave out what Strava did not return — an
    absent field is stored as NULL, never as 0. `synced_at` is set here."""
    try:
        if strava_id <= 0:
            return "FRODO: refused — strava_id must be a positive integer"
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            return "FRODO: refused — date must be YYYY-MM-DD"
        datetime.strptime(date, "%Y-%m-%d")
        if not sport_type.strip():
            return "FRODO: refused — sport_type is empty"
        row = dict(
            strava_id=strava_id, date=date, sport_type=sport_type.strip(), name=name,
            distance_m=distance_m, moving_time_s=moving_time_s, elapsed_time_s=elapsed_time_s,
            elevation_m=elevation_m, average_hr=average_hr, max_hr=max_hr,
            average_cadence=average_cadence, average_speed=average_speed,
            average_watts=average_watts, calories=calories, suffer_score=suffer_score,
            kilojoules=kilojoules, workout_type=workout_type,
            synced_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        negative = [k for k, v in row.items() if isinstance(v, (int, float)) and v < 0]
        if negative:
            return f"FRODO: refused — negative value in {', '.join(negative)}"
        db = _fitness_db()
        con = sqlite3.connect(db, timeout=10)
        try:
            con.execute(SCHEMA)
            existed = con.execute("SELECT 1 FROM activities WHERE strava_id = ?", (strava_id,)).fetchone()
            con.execute(
                f"INSERT OR REPLACE INTO activities ({', '.join(COLUMNS)}) "
                f"VALUES ({', '.join(':' + c for c in COLUMNS)})",
                row,
            )
            con.commit()
            total = con.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
        finally:
            con.close()
        nulls = [k for k in COLUMNS if row[k] is None]
        return (
            f"FRODO: {'replaced' if existed else 'inserted'} activity {strava_id} "
            f"({row['sport_type']}, {date}) in db/fitness.db — {total} rows in the table."
            + (f" Stored as NULL: {', '.join(nulls)}." if nulls else "")
        )
    except (ValueError, sqlite3.Error) as exc:
        return f"FRODO: refused — {exc}"


@server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def now() -> str:
    """The current local date and time. Use `iso` for `date:` / `updated:`
    frontmatter fields and `file` for timestamped file names."""
    t = datetime.now().astimezone()
    return (
        f"iso: {t.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"file: {t.strftime('%Y-%m-%dT%H-%M-%S')}\n"
        f"date: {t.strftime('%Y-%m-%d')} ({t.strftime('%A')}, UTC{t.strftime('%z')})"
    )


if __name__ == "__main__":
    server.run("stdio")
