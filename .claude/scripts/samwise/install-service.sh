#!/usr/bin/env bash
# Install (or refresh) the samwise-mcp user service from samwise-mcp.service.in,
# with this checkout's path filled in. Re-run after moving the repo or editing
# the template. The unit is copied, not linked, so switching branches never
# removes it. For it to start at boot without a login: loginctl enable-linger.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$unit_dir"
rm -f "$unit_dir/samwise-mcp.service"  # an older install linked it here
sed "s|@REPO_DIR@|$repo|g" "$here/samwise-mcp.service.in" > "$unit_dir/samwise-mcp.service"
systemctl --user daemon-reload
systemctl --user enable --now samwise-mcp.service
systemctl --user restart samwise-mcp.service
echo "samwise-mcp: installed for $repo — $(systemctl --user is-active samwise-mcp.service)"
