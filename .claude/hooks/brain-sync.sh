#!/usr/bin/env bash
# SessionStart hook: pull both repos on context boundary.
# Fail open — never block a session start.

GANDALF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$GANDALF_DIR/.claude/gandalf.env" 2>/dev/null || true

if [ -z "${BRAIN_PATH:-}" ]; then
  echo "brain-sync: BRAIN_PATH not set, skipping"
  exit 0
fi
BRAIN_DIR="$(cd "$GANDALF_DIR" && cd "$BRAIN_PATH" 2>/dev/null && pwd)" || {
  echo "brain-sync: BRAIN_PATH unreachable, skipping"; exit 0; }

LOCK="/tmp/gandalf-sync.lock"

sync_one() {
  local dir="$1" name="$2" before after
  before="$(git -C "$dir" rev-parse --short HEAD 2>/dev/null)" || {
    echo "$name: not a git repo"; return; }
  if ! git -C "$dir" pull --ff-only --quiet 2>/dev/null; then
    echo "$name: DIVERGED or offline — manual merge may be needed (at $before)"
    return
  fi
  after="$(git -C "$dir" rev-parse --short HEAD)"
  if [ "$before" = "$after" ]; then
    echo "$name: up to date ($after)"
  else
    echo "$name: $before -> $after"
  fi
}

exec 9>"$LOCK"
if flock -w 5 9; then
  sync_one "$GANDALF_DIR" gandalf
  sync_one "$BRAIN_DIR" brain
else
  echo "brain-sync: skipped, a job holds the lock"
fi

exit 0
