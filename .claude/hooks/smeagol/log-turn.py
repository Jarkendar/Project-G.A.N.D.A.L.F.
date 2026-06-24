#!/usr/bin/env python3
# S.M.E.A.G.O.L.'s query log. Installed as a Claude Code `Stop` hook (see
# .claude/settings.json) — fires once per turn, reads only this turn's slice of
# the session transcript, and appends one JSONL entry to
# brain/current/smeagol/YYYY-MM-DD.jsonl. Deterministic, no LLM call. Any
# failure is swallowed — this must never block or fail the user's turn.
#
# Schema is fixed by brain/current/smeagol/CLAUDE.md — keep the two in sync.

import json
import os
import sys
from datetime import datetime, timezone

AGENT_TOOL_NAMES = {"Agent", "Task"}


def read_brain_path(project_dir):
    env_file = os.path.join(project_dir, ".claude", "gandalf.env")
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("BRAIN_PATH="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def resolve_brain_dir(project_dir):
    raw = read_brain_path(project_dir)
    if not raw:
        return None
    path = raw if os.path.isabs(raw) else os.path.join(project_dir, raw)
    path = os.path.normpath(path)
    return path if os.path.isdir(path) else None


def load_transcript_lines(transcript_path):
    lines = []
    with open(transcript_path) as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return lines


def content_blocks(entry):
    content = (entry.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def is_genuine_user_prompt(entry):
    if entry.get("type") != "user":
        return False
    blocks = content_blocks(entry)
    return any(b.get("type") == "text" and b.get("text", "").strip() for b in blocks)


def find_turn_start(lines):
    for i in range(len(lines) - 1, -1, -1):
        if is_genuine_user_prompt(lines[i]):
            return i
    return 0


def classify_turn(lines):
    tool_uses = []
    for entry in lines:
        if entry.get("type") != "assistant":
            continue
        for block in content_blocks(entry):
            if block.get("type") == "tool_use":
                tool_uses.append((block.get("name") or "", block.get("input") or {}))

    agents_called = []
    for name, tool_input in tool_uses:
        if name in AGENT_TOOL_NAMES:
            agent_id = tool_input.get("subagent_type") or tool_input.get("description") or "unknown"
            if agent_id not in agents_called:
                agents_called.append(agent_id)

    skill_names = [ti.get("skill", "unknown") for name, ti in tool_uses if name == "Skill"]
    if skill_names:
        return f"skill:{skill_names[0]}", agents_called
    if agents_called:
        return f"agent:{agents_called[0]}", agents_called

    mcp_servers = [name.split("__", 2)[1] for name, _ in tool_uses if name.startswith("mcp__")]
    if mcp_servers:
        return f"mcp:{mcp_servers[0]}", agents_called

    touched_brain = any("brain/" in str(v) for _, ti in tool_uses for v in ti.values())
    if touched_brain:
        return "chat:brain-read", agents_called

    return "chat:general", agents_called


def latency_ms_since(start_ts):
    if not start_ts:
        return None
    try:
        start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
        return int((datetime.now(timezone.utc) - start_dt).total_seconds() * 1000)
    except ValueError:
        return None


def run():
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()

    if not session_id or not transcript_path or not os.path.isfile(transcript_path):
        return

    brain_dir = resolve_brain_dir(project_dir)
    if not brain_dir:
        return

    lines = load_transcript_lines(transcript_path)
    if not lines:
        return

    turn_lines = lines[find_turn_start(lines):]
    route, agents_called = classify_turn(turn_lines)
    latency_ms = latency_ms_since(turn_lines[0].get("timestamp"))

    now_local = datetime.now().astimezone()
    entry = {
        "timestamp": now_local.isoformat(timespec="seconds"),
        "session_id": session_id,
        "route": route,
        "agents_called": agents_called,
        "latency_ms": latency_ms,
        "outcome": "completed",
    }

    log_dir = os.path.join(brain_dir, "current", "smeagol")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, now_local.strftime("%Y-%m-%d") + ".jsonl")
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        pass
    sys.exit(0)
