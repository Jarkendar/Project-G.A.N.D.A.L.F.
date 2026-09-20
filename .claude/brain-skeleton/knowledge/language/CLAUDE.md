# CLAUDE.md — knowledge/language/

## Purpose
Language-learning practice logs and reference material. Currently: English
conversational practice (speaking + listening), fed by `/english-review` and
read by `/english-prep`.

## Privacy
**PRIVATE** — overrides the `knowledge/` public-by-default rule. This subtree
records self-assessed weaknesses tied to job interviews and real work calls
(see `english.md`), the same reasoning as `knowledge/career/gap-plan.md`.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Living documents — edit in place |
| `/english-review` skill | ✅ | Writes `english.md` after each session/call, one gate |
| `/english-prep` skill | read-only | Never writes; may seed `english-scenarios.md` if absent |
| Other CC agents | read-only | No writes |

## Files

| File | What it is |
|---|---|
| `english.md` | Living log — current focus, recurring error categories with counts, phrasebook, listening-miss log, session log |
| `english-scenarios.md` | Living scenario bank for practice sessions, tagged by error category |

## Notes
- Bump `date:` on every edit — both files are living documents, not append-only
  event records.
- `## Current focus` in `english.md` is derived (recomputed each write), not
  append-only — everything else in that file only grows.
- Raw transcripts are **not** stored here — `/ingest-conversation` archives
  those verbatim into `brain/conversations/`. This folder holds only the
  extracted signal.
