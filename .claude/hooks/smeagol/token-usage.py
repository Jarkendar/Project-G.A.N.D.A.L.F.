#!/usr/bin/env python3
# S.M.E.A.G.O.L.'s token ledger. Not a hook — a report run by hand:
#
#   .claude/hooks/smeagol/token-usage.py
#
# Reads this project's Claude Code transcripts (~/.claude/projects/<slug>/,
# kept ~30 days) and prints, per agent type and model: how many runs, the
# context size of the first turn ("start" — what it costs to launch), the
# context at the last turn, and the totals. The main session is one row per
# model. Read-only, no LLM call, nothing leaves the machine.
#
# Start = input + cache write + cache read of the first assistant turn, so it
# includes the caller's prompt. Compare runs before and after a change to an
# agent's tools or model, not single numbers.

import collections
import glob
import json
import os
import re
import statistics
import sys

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
TRANSCRIPTS = os.path.join(
    os.path.expanduser("~/.claude/projects"), re.sub(r"[^A-Za-z0-9]", "-", PROJECT_DIR)
)


def scan(path):
    """One transcript -> (model, date, [context per turn], totals)."""
    turns = {}  # message id -> usage of its last streamed chunk
    model = date = None
    with open(path, errors="ignore") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message", {})
            usage = msg.get("usage")
            if not usage or msg.get("model") == "<synthetic>":
                continue
            model = model or msg.get("model")
            date = date or d.get("timestamp", "")[:10]
            turns[msg.get("id")] = (
                usage.get("input_tokens", 0),
                usage.get("cache_creation_input_tokens", 0),
                usage.get("cache_read_input_tokens", 0),
                usage.get("output_tokens", 0),
            )
    contexts = [u[0] + u[1] + u[2] for u in turns.values()]
    totals = [sum(u[i] for u in turns.values()) for i in range(4)]
    return model, date, contexts, totals


def main():
    if not os.path.isdir(TRANSCRIPTS):
        sys.exit(f"no transcripts at {TRANSCRIPTS}")

    runs = collections.defaultdict(list)
    for path in glob.glob(os.path.join(TRANSCRIPTS, "*.jsonl")):
        model, date, contexts, totals = scan(path)
        if contexts:
            runs[("main session", model)].append((date, contexts, totals))
    for meta in glob.glob(os.path.join(TRANSCRIPTS, "*", "subagents", "*.meta.json")):
        path = meta[: -len(".meta.json")] + ".jsonl"
        if not os.path.exists(path):
            continue
        try:
            with open(meta) as f:
                agent = json.load(f).get("agentType", "?")
        except ValueError:
            continue
        model, date, contexts, totals = scan(path)
        if contexts:
            runs[(agent, model)].append((date, contexts, totals))

    print(f"{TRANSCRIPTS}\n")
    print(
        f"{'agent':16} {'model':26} {'runs':>4} {'turns':>6} {'start':>7} {'min':>7} {'max':>7}"
        f" {'end':>7} {'write M':>8} {'read M':>9} {'out M':>6}  dates"
    )
    order = sorted(runs.items(), key=lambda kv: -sum(r[2][1] + r[2][2] for r in kv[1]))
    for (agent, model), rs in order:
        starts = [r[1][0] for r in rs]
        ends = [r[1][-1] for r in rs]
        total = [sum(r[2][i] for r in rs) for i in range(4)]
        dates = sorted(r[0] for r in rs)
        print(
            f"{agent:16} {str(model):26} {len(rs):>4} {sum(len(r[1]) for r in rs):>6}"
            f" {int(statistics.median(starts)):>7} {min(starts):>7} {max(starts):>7}"
            f" {int(statistics.median(ends)):>7} {total[1] / 1e6:>8.2f} {total[2] / 1e6:>9.2f}"
            f" {total[3] / 1e6:>6.2f}  {dates[0]}..{dates[-1]}"
        )
    print("\nstart/min/max/end = context tokens (median start, median end); M = million tokens")


if __name__ == "__main__":
    main()
