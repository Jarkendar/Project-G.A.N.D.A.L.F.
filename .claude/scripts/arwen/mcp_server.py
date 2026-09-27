#!/usr/bin/env python3
# A.R.W.E.N. — Anki Repetition & Web-sync Engine for Notes.
#
# Anki as MCP tools — flashcards into the owner's Anki collection, which
# AnkiDroid shares through AnkiWeb.
#
# The Pi keeps its own copy of the collection (the official `anki` library, no
# GUI) and syncs it with AnkiWeb around every write; AnkiDroid syncs from
# there. AnkiWeb (with the phone behind it) is the source of truth, the Pi a
# relay:
#   - normal (incremental) sync: always — merges both sides;
#   - full download (AnkiWeb -> Pi): only while the Pi holds nothing unsynced
#     (a "dirty" flag spans every write until the sync after it succeeds);
#   - full upload (Pi -> AnkiWeb): never — it would overwrite the phone's
#     reviews. When AnkiWeb asks for it, the tools stop and say why.
#
# Tools: list_decks, find_notes, add_notes, sync. Cards are added as the stock
# note types (Basic, Basic and reversed, Cloze), found by their stock kind so
# a localized AnkiDroid ("Podstawowy", "Luka") matches too.
#
# Auth: login.py stores the AnkiWeb session key (never the password) in
# ~/.local/share/gandalf/arwen/auth.json, mode 600. Collection and state live
# next to it (ARWEN_DIR overrides). Each call opens the collection under a file
# lock and closes it, so parallel sessions never share an open collection.
#
# Run by Claude Code from .mcp.json (stdio).

import fcntl
import html
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from anki.collection import Collection
from anki.sync import SyncAuth
from anki.sync_pb2 import SyncCollectionResponse
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

ARWEN_DIR = Path(os.environ.get("ARWEN_DIR") or Path.home() / ".local/share/gandalf/arwen")
COLLECTION = ARWEN_DIR / "collection.anki2"
AUTH_FILE = ARWEN_DIR / "auth.json"
STATE_FILE = ARWEN_DIR / "state.json"
LOCK_FILE = ARWEN_DIR / ".lock"

GANDALF_TAG = "gandalf"
MAX_BATCH = 50
STOCK_KIND = {"basic": 1, "reversed": 2, "cloze": 5}  # notetype["originalStockKind"]
Required = SyncCollectionResponse.ChangesRequired

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)

server = MCPServer(
    name="arwen",
    log_level="WARNING",
    instructions=(
        "The owner's Anki collection (shared with AnkiDroid through AnkiWeb). Before adding, "
        "list_decks to place cards in an existing deck and find_notes to skip what is already "
        "there. Add only cards the owner approved. Everything added is synced to AnkiWeb, an "
        "external service: cards drawn from PRIVATE brain/ folders (core/, current/) need the "
        "owner's explicit yes first."
    ),
)


class SyncRefused(Exception):
    """A full sync the Pi must not do on its own."""


# --- state, auth, collection -----------------------------------------------------

def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, data: dict, private: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    if private:
        tmp.chmod(0o600)
    tmp.replace(path)


def _auth() -> SyncAuth | None:
    data = _read_json(AUTH_FILE)
    if not data.get("hkey"):
        return None
    return SyncAuth(hkey=data["hkey"], endpoint=data.get("endpoint") or None)


def _set_dirty(dirty: bool):
    _write_json(STATE_FILE, {**_read_json(STATE_FILE), "dirty": dirty})


@contextmanager
def _collection():
    """The collection, opened under an exclusive file lock and closed after."""
    ARWEN_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        col = Collection(str(COLLECTION))
        try:
            yield col
        finally:
            if col.db:
                col.close()


def _sync(col: Collection) -> str:
    """One sync with AnkiWeb under the policy above. Returns what happened;
    raises SyncRefused rather than risk the phone's data."""
    auth = _auth()
    if auth is None:
        raise SyncRefused("not logged in to AnkiWeb — run .claude/scripts/arwen/login.py once")
    out = col.sync_collection(auth, sync_media=False)
    if out.new_endpoint:
        _write_json(AUTH_FILE, {**_read_json(AUTH_FILE), "endpoint": out.new_endpoint}, private=True)
        auth = SyncAuth(hkey=auth.hkey, endpoint=out.new_endpoint)
    if out.required in (Required.NO_CHANGES, Required.NORMAL_SYNC):
        _set_dirty(False)
        return "synced"
    if out.required == Required.FULL_UPLOAD:
        raise SyncRefused("AnkiWeb holds no cards and asks for a full upload from the Pi — refused: "
                          "sync AnkiDroid first so AnkiWeb has the real collection")
    # FULL_DOWNLOAD (the Pi is empty) or FULL_SYNC (a conflict, e.g. a note type changed on the phone)
    if _read_json(STATE_FILE).get("dirty"):
        raise SyncRefused("AnkiWeb asks for a full sync while the Pi holds unsynced cards — refused: "
                          "a download would drop them, an upload would overwrite the phone's reviews. "
                          "Ask the owner how to proceed")
    col.close_for_full_sync()  # as Anki desktop does it; media are not synced, so no media usn
    col.full_upload_or_download(auth=auth, server_usn=None, upload=False)
    col.reopen(after_full_sync=True)
    _set_dirty(False)
    return "full download from AnkiWeb"


# --- notes ------------------------------------------------------------------------

class Card(BaseModel):
    deck: str = Field(description='Existing deck name, e.g. "Android::Kotlin"')
    kind: Literal["basic", "reversed", "cloze"] = "basic"
    front: str = Field(description="Question; for cloze the text with {{c1::...}} deletions")
    back: str = Field("", description="Answer; for cloze an optional extra shown after the answer")
    tags: list[str] = Field(default_factory=list, description="e.g. source:brain/knowledge/tech/x.md")


def _field_html(text: str) -> str:
    """Plain text with `code` spans and line breaks, as Anki field HTML."""
    parts = html.escape(text.strip()).split("`")
    out = "".join(f"<code>{p}</code>" if i % 2 else p for i, p in enumerate(parts))
    return out.replace("\n", "<br>")


def _notetype(col: Collection, kind: str) -> dict:
    stock = STOCK_KIND[kind]
    for model in col.models.all():
        if model.get("originalStockKind") == stock:
            return model
    raise ValueError(f"no stock '{kind}' note type in the collection")


def _deck_counts(col: Collection) -> list[dict]:
    decks = []
    for d in sorted(col.decks.all_names_and_ids(), key=lambda d: d.name):
        count = len(col.find_notes(f'deck:"{d.name}" -deck:"{d.name}::*"'))
        decks.append({"deck": d.name, "notes": count})
    return decks


def _refused(err: Exception) -> str:
    return f"ARWEN: {err}"


# --- tools ------------------------------------------------------------------------

@server.tool(annotations=READ)
def list_decks() -> str:
    """The owner's decks (synced from AnkiWeb first) with their note counts, one per line.
    Place new cards in the deck that fits; propose a new deck only when none does."""
    try:
        with _collection() as col:
            note = _sync(col)
            rows = [f"{d['deck']} — {d['notes']} notes" for d in _deck_counts(col)]
    except SyncRefused as err:
        return _refused(err)
    return f"({note})\n" + "\n".join(rows)


@server.tool(annotations=READ)
def find_notes(query: str, limit: int = 20) -> str:
    """Notes matching an Anki search (e.g. `"deck:Android*" coroutine`, `tag:gandalf`,
    `front:*StateFlow*`) — to check for cards that already exist before adding.
    Searches the Pi's copy, current as of the last sync."""
    with _collection() as col:
        ids = col.find_notes(query)
        lines = []
        for nid in ids[:limit]:
            note = col.get_note(nid)
            deck = col.decks.name(col.get_card(note.card_ids()[0]).did) if note.card_ids() else "?"
            fields = " | ".join(f[:80] for f in note.fields[:2])
            lines.append(f"{nid}  [{deck}]  {fields}")
    more = f"\n… {len(ids) - limit} more" if len(ids) > limit else ""
    return (f"{len(ids)} notes\n" + "\n".join(lines) + more) if ids else "0 notes"


@server.tool(annotations=WRITE)
def add_notes(cards: list[Card], allow_new_decks: bool = False) -> str:
    """Add approved cards, then sync them to AnkiWeb. Syncs first, so decks and
    duplicates are checked against the current collection.

    - Only cards the owner approved; at most 50 per call.
    - `deck` must exist unless `allow_new_decks` (only when the owner agreed to a new deck).
    - A card whose question already exists in its note type is skipped and reported.
    - Every card is tagged `gandalf` plus its own tags. Text may use `code` and line breaks.
    - kind: basic (question -> answer), reversed (both directions — vocabulary, terms),
      cloze (`front` holds {{c1::...}} deletions, `back` an optional extra).
    """
    if len(cards) > MAX_BATCH:
        return f"ARWEN: {len(cards)} cards — at most {MAX_BATCH} per call"
    try:
        with _collection() as col:
            before = _sync(col)
            existing = {d.name for d in col.decks.all_names_and_ids()}
            unknown = sorted({c.deck for c in cards} - existing)
            if unknown and not allow_new_decks:
                return f"ARWEN: no such deck(s): {', '.join(unknown)} — pick existing ones (list_decks) " \
                       f"or pass allow_new_decks after the owner agrees"
            added, skipped = [], []
            _set_dirty(True)
            for card in cards:
                note = col.new_note(_notetype(col, card.kind))
                note.fields[0] = _field_html(card.front)
                note.fields[1] = _field_html(card.back)
                note.tags = [GANDALF_TAG, *card.tags]
                problem = note.fields_check()
                if problem == 2:  # DUPLICATE
                    skipped.append(f"duplicate: {card.front[:60]}")
                    continue
                if problem:
                    skipped.append(f"{'empty' if problem == 1 else f'invalid ({problem})'}: {card.front[:60]}")
                    continue
                col.add_note(note, col.decks.id(card.deck))
                added.append(f"[{card.deck}] {card.front[:60]}")
            after = _sync(col)
    except SyncRefused as err:
        return _refused(err) + ("\n(cards added so far stay on the Pi and go out with the next sync)"
                                if _read_json(STATE_FILE).get("dirty") else "")
    except ValueError as err:
        return _refused(err)
    lines = [f"added {len(added)}, skipped {len(skipped)} (sync: {before}, then {after})"]
    lines += [f"+ {a}" for a in added] + [f"- {s}" for s in skipped]
    return "\n".join(lines)


@server.tool(annotations=WRITE)
def sync() -> str:
    """Sync the Pi's collection with AnkiWeb now (incremental; never a full upload)."""
    try:
        with _collection() as col:
            return f"ARWEN: {_sync(col)}"
    except SyncRefused as err:
        return _refused(err)


if __name__ == "__main__":
    server.run("stdio")
