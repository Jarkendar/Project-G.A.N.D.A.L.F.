# OpenACP ↔ Gandalf integration

Status: **PoC complete, verdict GO with conditions** (2026-07-05, dev machine,
not yet deployed to the target Raspberry Pi 5). This document is the
English-language architecture summary; the full bilingual PoC journal with
raw logs and incident-by-incident detail stays local as `poc-notes.md`
(git-ignored — see "Why the raw journal isn't here" below).

## What OpenACP is, and where it sits in the roadmap

**OpenACP** is a self-hosted bridge connecting a messaging platform
(Telegram, in this integration) to an ACP-compatible coding agent (Claude
Code, here). It lets Gandalf be driven headlessly from a phone, with no
keyboard on the dev machine.

In `IMPLEMENTATION.md` terms, this is **capability extension E1
(conversational gateway)**. E1 originally assumed an n8n flow (in the
`pi-automate` repo) as the channel substrate. OpenACP is an **alternative**
path to the same capability: a direct Telegram ↔ Claude Code bridge instead
of an n8n-mediated one. This PoC's purpose was to decide whether OpenACP
replaces the planned n8n path as the E1 foundation — verdict: yes, with the
conditions below.

## Architecture

```
Telegram (phone)
   │  message in a private supergroup, "Assistant" topic
   ▼
OpenACP bridge (npm package @openacp/cli, long-polling getUpdates)
   │  spawns/reuses a Claude Code headless session
   │  cwd = this repo (Gandalf workspace)
   ▼
Claude Code session
   │  reads CLAUDE.md, sees .claude/agents/*
   │  router decides: handle directly, or delegate to a sub-agent
   ▼
Sub-agent (e.g. Gimli/Samwise/Radagast) via the Task tool
   │
   ▼
Response streamed back through OpenACP → Telegram, with tool-calls visible
in the chat as they happen
```

Confirmed empirically (Faza 3 of the PoC): a session started through OpenACP
behaves exactly like an interactive Claude Code session in this workspace —
it reads `.claude/agents/`, explains its routing decision in the chat, and
invokes the real `Task` tool to hand off to a sub-agent. This was the
highest-risk hypothesis of the whole PoC and it held.

## Channel requirements (not what was originally assumed)

The original plan assumed a plain 1:1 private Telegram DM with the bot. In
practice, OpenACP requires a **Telegram supergroup with Forum/Topics enabled
and the bot promoted to admin** — `adminOk` checks fail otherwise. The
working setup is a small private group (owner + bot only), which keeps the
same access properties as a DM (nobody else can join or read) but is a
different Telegram object type than originally planned.

## Configuration

- `openacp.config.template` in this directory — sanitized, envsubst-ready
  version of the working `.openacp/config.json`. Real secrets (bot token,
  tunnel/JWT/API secrets, chat_id) live only in the git-ignored `.openacp/`
  workspace directory, never in this template.
- `openacp.service` in this directory — a systemd user unit **sketch**, not
  installed or enabled. For use once this moves to the Pi.

## Known issue: permission mode must be set explicitly

OpenACP's per-session ACP permission mode (`auto` / `default` / `acceptEdits`
/ `plan` / `dontAsk` / `bypassPermissions`) defaults to `auto` — a model
classifier approves or denies actions with **no visible prompt**. PoC testing
confirmed `auto` allows the agent to write files anywhere on the filesystem
(`/tmp`, `$HOME`, Desktop) without asking. **Before any production use, this
must be explicitly forced to `default` or `dontAsk`** — do not rely on the
`auto` default. This is a configuration fix, not an architectural one.

## Known issue: default third-party tunnel

From first run, OpenACP stands up an outbound Cloudflare tunnel through its
own hosting (`tunnel-<hash>.openacp.ai`, label "system") for its Daemon
API / Remote Access feature — without the user opting in. Two things about
this matter, and one thing doesn't:

- **Doesn't matter much:** the tunnel itself as a mechanism. Core Telegram
  messaging (long-polling `getUpdates`) does **not** route through it — it's
  only used by the optional Daemon API / Remote Access feature, which this
  integration doesn't use.
- **Does matter:** it's on **by default, without explicit consent**, and it's
  operated by a **third party whose source was unverifiable** during this PoC
  (`github.com/Open-ACP/OpenACP` returned 404 throughout).

Verdict: accepted as a documented MVP exception — the same shape as the
existing Claude-API/`brain` privacy exception already documented in
`CLAUDE.md` — because it doesn't touch the tested message path. Revisit
before the Pi migration: can it be disabled while the Daemon API feature
stays unused, and is the operator trustworthy enough to keep accepting by
then.

## PoC verdict

**GO, with conditions.** The highest-risk hypothesis (Gandalf's router and
sub-agents work correctly through the bridge) is confirmed. Three items must
be closed before production/Pi migration:

1. Force permission mode to `default`/`dontAsk` (see above) — config fix.
2. Decide on the default tunnel (see above) — trust/architecture decision,
   not a blocker.
3. The upstream OpenACP source being unverifiable for the whole PoC is a
   standing trust factor for a third-party tool with deep filesystem and
   session access — worth a standalone decision (accept vs. look at
   alternatives) independent of this PoC's scope.

Also confirmed: fail-closed behavior for an unauthorized chat_id is strong
(silent drop, zero log entries, not just a denial), session continuity works
correctly, and the bridge self-heals from transient Telegram auth failures
(observed 401 → auto-restart within ~35s after a token rotation).

## Before the Pi migration

1. Force `default`/`dontAsk` permission mode in session config.
2. Resolve the default-tunnel question above.
3. Decide whether OpenACP's unverifiable upstream source is acceptable for a
   production deployment, or look at alternatives.
4. Test behavior across a real system reboot (this PoC only tested process
   restarts, not `.openacp/` persistence across a full reboot).
5. Build `bootstrap.sh` from the PoC steps, accounting for ARM/RPi 5
   differences (node/nvm paths, performance).
6. Plan artifact delivery (e.g. `.md` reports) via Faramir/n8n — OpenACP has
   no native file-attachment delivery to Telegram.

## Why the raw journal isn't here

`poc-notes.md` (repo root, git-ignored) is the full bilingual PoC journal:
every phase, every test, every incident, with logs. It stays local and
ignored because (a) it was written incrementally over a live PoC and may
carry secret fragments in transit even after scanning, and (b) it's in
Polish, which doesn't match this repo's "artifacts in English" convention.
This file is the durable, English, sanitized takeaway; the journal is the
working notebook behind it.
