# CLAUDE.md — current/smeagol/

## Purpose
Append-only query log for every G.A.N.D.A.L.F. interaction. Written by
S.M.E.A.G.O.L., read by T.R.E.E.B.E.A.R.D. and future analytics agents.

## Privacy level
**PRIVATE** — entries carry only routing/timing metadata plus a `session_id`
pointer back to the full Claude Code session transcript (which holds the actual
query content). The pointer alone is enough to correlate and, in batch, pull full
content for analysis — so it stays PRIVATE even though no raw query text lives
in this file.

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
Fields: `timestamp`, `session_id`, `route`, `agents_called`, `latency_ms`, `outcome`

## Notes for Claude Code
Read-only for all agents except S.M.E.A.G.O.L.
Written by a deterministic `Stop` hook (no LLM call) — see
`.claude/hooks/smeagol/log-turn.py`. Future batch analysis (topic classification
over un-routed entries) follows `session_id` to the matching Claude Code session
transcript and must run through a **local** model only — never send transcript
content to an external API for this.
