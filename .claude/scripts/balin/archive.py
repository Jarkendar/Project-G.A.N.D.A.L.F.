# B.A.L.I.N. — the logic of `archive_transcripts`, stdlib only (the MCP wrapper is
# mcp_server.py; this file is split off so it can be tested with a plain python3).
#
# What /ingest-conversation does for a transcript in the drop folder — a
# frontmatter'd file in brain/conversations/, deduplicated by content hash — done
# for the transcripts of an `english-review`, without a shell. The format is the
# one of brain/conversations/CLAUDE.md, with `source: agent` in place of
# `source: bookmarklet`.
#
# It writes new files into brain/conversations/ and nothing else: never an
# existing file, never another folder, never a missing conversations/ folder.

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

MAX_ITEMS = 10
MAX_TITLE = 60
MAX_SLUG = 40
MAX_TAGS = 6
MAX_TRANSCRIPT = 2 * 1024 * 1024
SOURCE = "agent"
BASE_TAG = "english-review"
STOP_WORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "with", "my", "is",
    "i", "w", "z", "na", "do", "i", "oraz", "o", "po", "ze", "się", "sie",
}
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
HASH_RE = re.compile(r"^content_hash: (sha256:[0-9a-f]{64})\s*$", re.MULTILINE)


class Refused(Exception):
    pass


def digest(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_variants(text: str) -> list[str]:
    # A pasted transcript may differ from the dropped file by its last newline only.
    seen, out = set(), []
    for variant in (text, text.rstrip(), text.rstrip("\n"), text.rstrip() + "\n"):
        h = digest(variant)
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def assistant_of(text: str) -> str:
    claude = sum(1 for line in text.split("\n") if line.startswith("Claude: "))
    gemini = sum(1 for line in text.split("\n") if line.startswith("Gemini: "))
    if claude > gemini:
        return "claude"
    if gemini > claude:
        return "gemini"
    return "unknown"


def slugify(title: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", title.replace("ł", "l").replace("Ł", "L"))
    ascii_ = ascii_.encode("ascii", "ignore").decode().lower()
    words = [w for w in re.sub(r"[^a-z0-9]+", " ", ascii_).split() if w not in STOP_WORDS]
    slug = "-".join(words)[:MAX_SLUG].strip("-")
    if not slug:
        raise Refused(f"the title {title!r} leaves no slug")
    return slug


def parse_now(now: str) -> datetime:
    try:
        return datetime.fromisoformat(now.strip()).replace(tzinfo=None, microsecond=0)
    except ValueError:
        raise Refused(f"now must be an ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS), got {now!r}")


def existing_hashes(folder: Path) -> dict[str, str]:
    found = {}
    for path in sorted(folder.glob("*.md")):
        try:
            head = path.read_text(encoding="utf-8")[:4000]
        except (OSError, UnicodeDecodeError):
            continue
        match = HASH_RE.search(head)
        if match:
            found[match.group(1)] = path.name
    return found


def _clean(item: object, index: int) -> dict:
    if not isinstance(item, dict):
        raise Refused(f"item {index}: not an object")
    title = str(item.get("title") or "").strip().replace('"', "'")
    summary = str(item.get("summary") or "").strip()
    transcript = item.get("transcript")
    tags = item.get("tags")
    if not title or len(title) > MAX_TITLE or "\n" in title:
        raise Refused(f"item {index}: the title must be one line of 1–{MAX_TITLE} characters")
    if not summary:
        raise Refused(f"item {index}: a summary is required")
    if not isinstance(transcript, str) or not transcript.strip():
        raise Refused(f"item {index}: the transcript is empty")
    if len(transcript.encode("utf-8")) > MAX_TRANSCRIPT:
        raise Refused(f"item {index}: the transcript is larger than {MAX_TRANSCRIPT // (1024 * 1024)} MB")
    if not isinstance(tags, list) or not tags:
        raise Refused(f"item {index}: at least one tag is required")
    clean_tags = []
    for tag in tags:
        tag = str(tag).strip().lower()
        if not TAG_RE.match(tag):
            raise Refused(f"item {index}: tag {tag!r} is not lowercase kebab-case")
        if tag not in clean_tags:
            clean_tags.append(tag)
    return {"title": title, "summary": summary, "transcript": transcript, "tags": clean_tags}


def _render(item: dict, stamp: datetime, assistant: str, hash_: str) -> str:
    tags = list(item["tags"])
    extra = [BASE_TAG] + ([assistant] if assistant != "unknown" else [])
    tags = (extra + [t for t in tags if t not in extra])[:MAX_TAGS]
    return (
        "---\n"
        f"date: {stamp.strftime('%Y-%m-%dT%H:%M:%S')}\n"
        f"source: {SOURCE}\n"
        f"assistant: {assistant}\n"
        "privacy: private\n"
        f"tags: [{', '.join(tags)}]\n"
        f"content_hash: {hash_}\n"
        f"title: \"{item['title']}\"\n"
        "---\n\n"
        "## Summary\n\n"
        f"{item['summary']}\n\n"
        "## Transcript\n\n"
        f"{item['transcript']}"
    )


def archive(brain: Path, items: list, now: str, dry_run: bool = False) -> list[dict]:
    """Plan (and, unless dry_run, write) one file per item. Returns, per item:
    name, path, title, assistant, tags, content_hash, lines, chars, duplicate_of."""
    folder = brain / "conversations"
    if not folder.is_dir():
        raise Refused(f"{folder} does not exist — run /init-brain first; this tool never creates the folder")
    if not isinstance(items, list) or not items:
        raise Refused("no transcripts given")
    if len(items) > MAX_ITEMS:
        raise Refused(f"more than {MAX_ITEMS} transcripts in one call")
    base = parse_now(now)
    known = existing_hashes(folder)
    batch: dict[str, int] = {}
    plan = []
    for index, raw in enumerate(items, 1):
        item = _clean(raw, index)
        variants = hash_variants(item["transcript"])
        hash_ = variants[0]
        dup = next((known[h] for h in variants if h in known), None)
        if dup is None:
            earlier = next((batch[h] for h in variants if h in batch), None)
            if earlier is not None:
                dup = f"item {earlier} of this call"
        batch.setdefault(hash_, index)
        stamp = base + timedelta(seconds=index - 1)
        assistant = assistant_of(item["transcript"])
        name = f"{stamp.strftime('%Y-%m-%dT%H-%M-%S')}_{SOURCE}_{slugify(item['title'])}.md"
        target = folder / name
        if dup is None and target.exists():
            raise Refused(f"item {index}: {name} already exists — an archived transcript is never overwritten")
        plan.append({
            "index": index, "name": name, "path": target, "title": item["title"],
            "assistant": assistant, "content_hash": hash_, "duplicate_of": dup,
            "lines": item["transcript"].count("\n") + 1, "chars": len(item["transcript"]),
            "text": None if dup else _render(item, stamp, assistant, hash_),
            "transcript": item["transcript"],
        })
    if dry_run:
        return plan
    done = []
    try:
        for entry in plan:
            if entry["duplicate_of"]:
                continue
            with open(entry["path"], "x", encoding="utf-8", newline="") as fh:
                fh.write(entry["text"])
            done.append(entry["path"])
            with open(entry["path"], encoding="utf-8", newline="") as fh:
                written = fh.read()
            if not written.endswith("## Transcript\n\n" + entry["transcript"]):
                raise Refused(f"{entry['name']}: the file read back does not end with the transcript as given")
    except (OSError, Refused):
        # Whole or nothing: what this call created is taken back (own new files only).
        for path in done:
            path.unlink(missing_ok=True)
        raise
    return plan
