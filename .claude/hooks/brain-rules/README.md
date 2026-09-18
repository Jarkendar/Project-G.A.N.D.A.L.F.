# brain-rules — making brain/'s CLAUDE.md files visible

`brain/` describes itself: every folder's rules (privacy, schema, naming,
writers) live in that folder's `CLAUDE.md`, **and only there**. Other tools
working inside `brain/` read them directly.

Claude Code sessions of *this* project do not. `brain/` is a sibling
directory, not part of the project tree, so Claude Code never loads its
`CLAUDE.md` files by itself. `inject.py` closes that gap by handing the rules
to the session through hooks. It never copies them anywhere.

## Why a hook (verified 2026-09-18 on Claude Code 2.1.276)

| Mechanism | brain/CLAUDE.md (root) | Folder rules (`knowledge/events/CLAUDE.md` …) |
|---|---|---|
| Nothing (plain session) | ❌ | ❌ |
| `--add-dir ../brain` | ❌ | ❌ |
| `--add-dir` + env `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1` | ✅ only as launch flags, not via `settings.json` | ❌ |
| `@../brain/CLAUDE.md` import in project `CLAUDE.md` | ❌ in headless `claude -p` | ❌ |
| **This hook** | ✅ | ✅ |

The hook lives in the project's `.claude/settings.json`, so it applies to every
session started in this directory: interactive, Remote Control,
`gandalf.service`, headless `claude -p` from cron. No launcher changes needed.

## How it works

| Event | Matcher | Injects |
|---|---|---|
| `SessionStart` (startup, resume, `/clear`, compaction) | — | resolved `BRAIN_PATH` + `brain/CLAUDE.md` + a note about how folder rules arrive |
| `PostToolUse` | `Read\|Edit\|Glob\|Grep` | `CLAUDE.md` chain from the brain/ root down to the touched folder |
| `PreToolUse` | `Write` | same chain for the target folder of a new file |

- Each rule file is injected **at most once per session**. The state lives in
  `$TMPDIR/gandalf-brain-rules-<session_id>.json` and is reset on every
  `SessionStart`, so after `/clear` or compaction the rules come back.
- `BRAIN_PATH` is read from `.claude/gandalf.env`. If it is missing or the
  directory does not exist, the hook does nothing.
- Any error is swallowed (exit 0). The hook never blocks a tool call or a
  session.

## Known limits

- **Bash access does not trigger it.** `cat`, `grep`, `sqlite3` or `python`
  touching brain/ files bring no folder rules. Before *writing* to a folder
  via Bash, `Read` its `CLAUDE.md` first. The `SessionStart` note says the
  same to the model.
- **`Write` of a new file:** the `PreToolUse` context arrives together with the
  tool result, not before the write. The model sees the folder rules right
  after its first write there and can correct the file, but it did not have
  them for that first write. `Edit` has no such gap, because it requires an
  earlier `Read`.
- **Token cost:** root rules on every session start, plus each folder's rules
  once per session on first touch.

## What to do when…

- **Adding a new folder to brain/:** write its `CLAUDE.md` in brain/. Nothing to
  register here, because the hook discovers rule files by walking up the
  directory tree.
- **Changing folder rules:** edit the `CLAUDE.md` in brain/ and commit it in
  brain/. There is no copy to update. `.claude/brain-skeleton/` holds only data
  templates (`core/` living documents, `_meta/*.json`, empty folders).
- **A skill needs rules before writing via Bash:** make the skill `Read` the
  folder's `CLAUDE.md` explicitly (as `/daily`, `/idea` and Gimli already do).
- **Debugging:** run the hook by hand and check its JSON output:

  ```bash
  echo '{"hook_event_name":"SessionStart","session_id":"debug"}' \
    | CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/brain-rules/inject.py
  echo '{"hook_event_name":"PostToolUse","session_id":"debug","tool_input":{"file_path":"../brain/db/CLAUDE.md"}}' \
    | CLAUDE_PROJECT_DIR="$PWD" .claude/hooks/brain-rules/inject.py
  ```

  No output means nothing new to inject (already seen in this session, a path
  outside brain/, or an unresolved `BRAIN_PATH`). Delete
  `$TMPDIR/gandalf-brain-rules-debug.json` to repeat.

## Not done yet: scaffolding a new brain/ with rules

`/init-brain` creation mode now builds only the data structure. A fresh brain/
starts without any `CLAUDE.md`. This does not matter while there is one brain/
(a new machine clones the brain/ repo, rules included). It matters once someone
else wants to start from this public repo. See IMPLEMENTATION.md, parking lot
"brain/ rules — scaffolding a new brain/", for the design worked out when this
was deferred.
