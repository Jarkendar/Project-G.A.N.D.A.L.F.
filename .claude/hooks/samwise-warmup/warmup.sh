#!/usr/bin/env bash
# SessionStart hook: asks the S.A.M.W.I.S.E. HTTP server to start its worker
# (POST /warmup returns at once, the ~15 s model load runs in the background),
# so the first question of the session does not wait for it. The server's
# idle unload (SAMWISE_IDLE_UNLOAD) frees the RAM again if nothing is asked.
# Silent and never failing: no server running means no warm-up, nothing more.

curl -s -o /dev/null -m 2 -X POST "${SAMWISE_URL:-http://127.0.0.1:8765}/warmup" || true
exit 0
