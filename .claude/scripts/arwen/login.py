#!/usr/bin/env python3
# A.R.W.E.N. — one-time AnkiWeb login for the Anki MCP server. Asks for the AnkiWeb e-mail
# and password in the terminal, exchanges them for a session key and stores
# only the key (mode 600) — the password is never written anywhere. Then
# runs the first sync, a full download of the collection from AnkiWeb.
#
# Run in a terminal (the password prompt needs one):
#   .claude/scripts/arwen/.venv/bin/python .claude/scripts/arwen/login.py
# Re-run after changing the AnkiWeb password; `--logout` forgets the key.

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mcp_server as arwen  # noqa: E402


def main():
    if "--logout" in sys.argv:
        arwen.AUTH_FILE.unlink(missing_ok=True)
        print("ARWEN: logged out — the session key is gone.")
        return
    if not sys.stdin.isatty():
        sys.exit("ARWEN: run this in a terminal — it asks for the AnkiWeb password.")
    user = input("AnkiWeb e-mail: ").strip()
    password = getpass.getpass("AnkiWeb password: ")
    with arwen._collection() as col:
        auth = col.sync_login(user, password, endpoint=None)
        arwen._write_json(arwen.AUTH_FILE, {"hkey": auth.hkey, "endpoint": auth.endpoint}, private=True)
        print(f"ARWEN: logged in; session key saved to {arwen.AUTH_FILE} (mode 600).")
        try:
            print(f"ARWEN: first sync — {arwen._sync(col)}.")
        except arwen.SyncRefused as err:
            sys.exit(f"ARWEN: {err}")
        print("ARWEN: decks now on the Pi:")
        for d in arwen._deck_counts(col):
            print(f"  {d['deck']} — {d['notes']} notes")


if __name__ == "__main__":
    main()
