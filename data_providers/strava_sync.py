#!/usr/bin/env python3
"""
Strava → brain/db/fitness.db  — one batch at a time.

Modes:
  status          show DB state and what's left to sync
  sync            fetch + insert next batch of 50 (initial sync: oldest page not yet done)
  sync --incremental   fetch activities newer than last record in DB

Run from this repo root:
  python data_providers/strava_sync.py status
  python data_providers/strava_sync.py sync
"""
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── paths ────────────────────────────────────────────────────────────────────

_HERE      = Path(__file__).parent
_REPO_ROOT = _HERE.parent
_ENV_FILE  = _REPO_ROOT / ".claude/gandalf.env"
_MCP_TOKEN = Path.home() / ".config/strava-mcp/config.json"

BATCH_SIZE = 50
API_BASE   = "https://www.strava.com/api/v3"
TOKEN_URL  = "https://www.strava.com/oauth/token"

# ── config ───────────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _brain_db(env: dict) -> Path:
    raw = env.get("BRAIN_PATH", "../brain")
    base = Path(raw) if Path(raw).is_absolute() else (_REPO_ROOT / raw)
    return base.resolve() / "db/fitness.db"


# ── token ────────────────────────────────────────────────────────────────────

def _get_token(env: dict) -> str:
    cfg = json.loads(_MCP_TOKEN.read_text())
    if cfg.get("expiresAt", 0) > int(time.time()) + 60:
        return cfg["accessToken"]

    resp = requests.post(TOKEN_URL, data={
        "client_id":     env["STRAVA_CLIENT_ID"],
        "client_secret": env["STRAVA_CLIENT_SECRET"],
        "grant_type":    "refresh_token",
        "refresh_token": cfg["refreshToken"],
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    cfg.update(accessToken=data["access_token"],
                refreshToken=data["refresh_token"],
                expiresAt=data["expires_at"])
    _MCP_TOKEN.write_text(json.dumps(cfg, indent=2))
    print("  token refreshed")
    return cfg["accessToken"]


# ── Strava API ───────────────────────────────────────────────────────────────

def _fetch(token: str, params: dict) -> list[dict]:
    r = requests.get(f"{API_BASE}/athlete/activities",
                     headers={"Authorization": f"Bearer {token}"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def _map(a: dict, now: str) -> dict:
    return {
        "strava_id":      a["id"],
        "date":           (a.get("start_date_local") or "")[:10],
        "sport_type":     a.get("sport_type") or a.get("type"),
        "name":           a.get("name"),
        "distance_m":     a.get("distance"),
        "moving_time_s":  a.get("moving_time"),
        "elapsed_time_s": a.get("elapsed_time"),
        "elevation_m":    a.get("total_elevation_gain"),
        "average_hr":     a.get("average_heartrate"),
        "max_hr":         a.get("max_heartrate"),
        "average_cadence":a.get("average_cadence"),
        "average_speed":  a.get("average_speed"),
        "average_watts":  a.get("average_watts"),
        "calories":       a.get("calories"),
        "suffer_score":   a.get("suffer_score"),
        "kilojoules":     a.get("kilojoules"),
        "workout_type":   a.get("workout_type"),
        "synced_at":      now,
    }


# ── DB ───────────────────────────────────────────────────────────────────────

_UPSERT = """
INSERT OR REPLACE INTO activities
  (strava_id, date, sport_type, name,
   distance_m, moving_time_s, elapsed_time_s, elevation_m,
   average_hr, max_hr, average_cadence, average_speed,
   average_watts, calories, suffer_score, kilojoules,
   workout_type, synced_at)
VALUES
  (:strava_id, :date, :sport_type, :name,
   :distance_m, :moving_time_s, :elapsed_time_s, :elevation_m,
   :average_hr, :max_hr, :average_cadence, :average_speed,
   :average_watts, :calories, :suffer_score, :kilojoules,
   :workout_type, :synced_at)
"""


def _db_stats(db: Path) -> dict:
    con = sqlite3.connect(db)
    total = con.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    oldest = con.execute("SELECT MIN(date) FROM activities").fetchone()[0]
    newest = con.execute("SELECT MAX(date) FROM activities").fetchone()[0]
    con.close()
    return {"total": total, "oldest": oldest, "newest": newest}


def _insert(db: Path, rows: list[dict]) -> int:
    con = sqlite3.connect(db)
    con.executemany(_UPSERT, rows)
    con.commit()
    n = con.total_changes
    con.close()
    return n


# ── commands ─────────────────────────────────────────────────────────────────

def cmd_status(db: Path, env: dict):
    stats = _db_stats(db)
    print(f"fitness.db  →  {stats['total']} activities")
    if stats["total"]:
        print(f"  range : {stats['oldest']} → {stats['newest']}")

    token = _get_token(env)
    # quick probe: how many total on Strava (first page to check if more exist)
    first = _fetch(token, {"per_page": 1, "page": 1})
    if not first:
        print("  Strava: no activities found")
        return

    # Check next page; if it returns fewer than BATCH_SIZE it's the last page —
    # cross-check IDs to see if they're already in DB.
    next_page = stats["total"] // BATCH_SIZE + 1
    probe = _fetch(token, {"per_page": BATCH_SIZE, "page": next_page})
    if not probe:
        print("  Strava: ✅ DB up to date")
    elif len(probe) < BATCH_SIZE:
        # Last partial page — check if all its IDs are already in DB
        con = sqlite3.connect(db)
        probe_ids = {a["id"] for a in probe}
        existing  = {r[0] for r in con.execute(
            f"SELECT strava_id FROM activities WHERE strava_id IN ({','.join('?'*len(probe_ids))})",
            list(probe_ids)
        )}
        con.close()
        if probe_ids == existing:
            print(f"  Strava: ✅ DB up to date (last page {next_page} already synced)")
        else:
            missing = len(probe_ids - existing)
            print(f"  Strava: ⏳ last page {next_page} has {missing} unsynced activities")
    else:
        print(f"  Strava: ⏳ more to sync — next batch is page {next_page}")


def cmd_sync(db: Path, env: dict, incremental: bool = False):
    stats = _db_stats(db)
    token = _get_token(env)
    now   = datetime.now(timezone.utc).isoformat()

    if incremental and stats["newest"]:
        # fetch only activities after newest in DB
        import calendar
        dt = datetime.strptime(stats["newest"], "%Y-%m-%d")
        after_ts = int(calendar.timegm(dt.timetuple()))
        print(f"Incremental sync: fetching activities after {stats['newest']}")
        activities = _fetch(token, {"per_page": BATCH_SIZE, "after": after_ts})
    else:
        # initial sync: next page not yet in DB
        next_page = stats["total"] // BATCH_SIZE + 1
        print(f"Initial sync: fetching page {next_page} "
              f"(DB has {stats['total']} rows, batch size {BATCH_SIZE})")
        activities = _fetch(token, {"per_page": BATCH_SIZE, "page": next_page})

    if not activities:
        print("Nothing to sync — already up to date.")
        return

    rows     = [_map(a, now) for a in activities]
    inserted = _insert(db, rows)
    new_stats = _db_stats(db)

    print(f"  fetched  : {len(activities)}")
    print(f"  upserted : {inserted}")
    print(f"  DB total : {new_stats['total']}  ({new_stats['oldest']} → {new_stats['newest']})")

    if len(activities) < BATCH_SIZE:
        print(f"\n  ✅ Full sync complete")
    else:
        print(f"\n  ⏳ More to sync — run again for next batch")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    env = _load_env()
    db  = _brain_db(env)

    if not db.exists():
        print(f"ERROR: {db} not found — create it first (schema in IMPLEMENTATION.md)")
        sys.exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    incremental = "--incremental" in sys.argv

    if mode == "status":
        cmd_status(db, env)
    elif mode == "sync":
        cmd_sync(db, env, incremental=incremental)
    else:
        print(f"Unknown mode: {mode}. Use: status | sync [--incremental]")
        sys.exit(1)
