# CLAUDE.md — current/smeagol/

## Purpose
Append-only query log for every G.A.N.D.A.L.F. interaction. Written by
S.M.E.A.G.O.L., read by T.R.E.E.B.E.A.R.D. and future analytics agents.

## Privacy level
**PRIVATE** — logs contain query content and routing details.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| S.M.E.A.G.O.L. | ✅ | Append-only — one entry per Gandalf query |
| T.R.E.E.B.E.A.R.D. | ❌ | Read-only |
| User (manual) | ❌ | Do not edit logs manually |
| Any other source | ❌ | Not allowed |

## Allowed
- Appending new log entries (S.M.E.A.G.O.L. only)
- Reading for analysis

## Not allowed
- Modifying or deleting existing entries — ever
- Retroactive edits of any kind

## File format
JSONL: one JSON object per line, one file per day.
Naming: `YYYY-MM-DD.jsonl`
Fields: `timestamp`, `query_hash`, `route`, `agents_called`, `latency_ms`, `outcome`

## Notes for Claude Code
Read-only for all agents except S.M.E.A.G.O.L.
Do not include log content in API context — use locally only for analysis.
