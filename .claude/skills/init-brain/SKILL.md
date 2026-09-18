---
name: init-brain
description: >-
  Initialize or validate the brain/ knowledge repository for G.A.N.D.A.L.F.
  from the data skeleton at .claude/brain-skeleton/ (living-document
  templates, _meta files, empty folders). Use this skill for first-time setup
  when brain/ does not exist yet, after cloning this repo on a new machine, to
  validate that an existing brain/ has the expected structure, or to recover
  missing core/ templates or _meta files.
---

# init-brain

Initialize or validate the `brain/` knowledge repository for G.A.N.D.A.L.F.

## When to use

- First-time setup: `brain/` does not exist yet
- After cloning this repo on a new machine
- Validating that an existing `brain/` has the correct structure
- Recovering missing `core/` templates or `_meta/` files

---

## Steps

### 1. Resolve BRAIN_PATH

Read `.claude/gandalf.env` from this project's root. Extract `BRAIN_PATH`.

If the file does not exist:
- Tell the user: "`.claude/gandalf.env` not found. Copy `.claude/gandalf.env.example`
  to `.claude/gandalf.env` and set `BRAIN_PATH` to the path of your brain/ repo."
- Stop.

If `BRAIN_PATH` is not set or empty:
- Tell the user to set `BRAIN_PATH` in `.claude/gandalf.env`.
- Stop.

Resolve the path (expand `~`, resolve relative paths from the project root).
Call it `$BRAIN`.

### 2. Check existence

If `$BRAIN` exists:
- Run **Validation mode** (Step 4).
- Then run **Step 5** (hooks wiring).

If `$BRAIN` does not exist:
- Tell the user the resolved path and ask: "brain/ not found at `$BRAIN`. Create scaffold?"
- On confirmation: run **Creation mode** (Step 3), then **Step 5** (hooks wiring).
- On refusal: stop.

### 3. Creation mode

Copy the skeleton tree into `$BRAIN`:

```bash
cp -rn <PROJECT_ROOT>/.claude/brain-skeleton/. "$BRAIN/"
```

`-r` copies recursively; `-n` (no-clobber) never overwrites an existing file —
safe to run on a partially-initialised brain. `.` copies hidden files (`.gitkeep`).

Resolve `<PROJECT_ROOT>` to the absolute path of this G.A.N.D.A.L.F. repo
(the directory containing `.claude/`).

After copying, print a summary: `find "$BRAIN" -type f | sort`.

### 4. Validation mode

Derive the expected file list from the skeleton:

```bash
find <PROJECT_ROOT>/.claude/brain-skeleton -type f -printf '%P\n' | sort
```

For each relative path `<relpath>` in that list:
- Check if `$BRAIN/<relpath>` exists.
- If missing: offer to copy it from the skeleton:
  `cp -n <PROJECT_ROOT>/.claude/brain-skeleton/<relpath> "$BRAIN/<relpath>"`

Validation checks **existence only** — documents in `core/` are living documents
and will diverge from the skeleton template intentionally. Do not check content.

Print validation report: ✅ present / ❌ missing for each path.

Then list every folder in `$BRAIN` (excluding `.git/`) that has no `CLAUDE.md`
of its own **and** no ancestor below the root that has one — report these as
⚠️ "no folder rules". Report only; never create rule files from this skill.

### 5. Hooks wiring

`$BRAIN` is a separate git repo and is meant to hold data only — no executable
code (see `brain/CLAUDE.md`). The frontmatter validator hook therefore lives in
*this* repo, at `.claude/hooks/brain/pre-commit`, and `$BRAIN` must be pointed
at it via `core.hooksPath`.

Check the current value:

```bash
git -C "$BRAIN" config --get core.hooksPath
```

Resolve `<PROJECT_ROOT>` to the absolute path of this G.A.N.D.A.L.F. repo (same
as Step 3) and compute the target: `<PROJECT_ROOT>/.claude/hooks/brain`.

- If the current value already equals the target: report "git hooks already wired."
- Otherwise, set it and report the change (mention the previous value if it was non-empty):

```bash
git -C "$BRAIN" config core.hooksPath "<PROJECT_ROOT>/.claude/hooks/brain"
```

This uses an absolute path on purpose — `core.hooksPath` isn't portable across
machines as a relative path here ($BRAIN and this repo are independently
located), and `$BRAIN`'s location is already re-resolved per machine via
`gandalf.env` in Step 1. Re-running this step is idempotent.

---

## Notes

- **Skeleton source.** Data templates (living documents in `core/`, `_meta/`
  files, empty folders) live in `.claude/brain-skeleton/` in this repo. To add or
  change one, edit the file there — not here.
- **Rules are not in the skeleton.** Every `CLAUDE.md` and `_meta/schema.md` lives
  **only** in `brain/` — brain/ describes itself, and other tools working inside
  brain/ rely on that. Sessions of this project see those rules through the
  `.claude/hooks/brain-rules/inject.py` hook (root rules at session start, folder
  rules on first touch). A freshly created brain/ therefore starts without rule
  files — see IMPLEMENTATION.md, parking lot "brain/ rules — scaffolding a new
  brain/", for the deferred export design.
- **No-clobber by design.** Both creation and validation use `-n` / `cp -n`. Existing
  files in brain/ are never overwritten by this skill. This is intentional: living
  documents (core/) accumulate real data and must not be reset.
- **Validation scope.** Validation only checks structural completeness (all skeleton
  files present). It does not verify frontmatter, content, or that living documents
  match the template — they are not supposed to after the first edit.
- **Hooks source.** The pre-commit frontmatter validator run via `core.hooksPath`
  lives at `.claude/hooks/brain/pre-commit` in this repo, not in `brain/` — see
  Step 5. It can always be bypassed per-commit with `git commit --no-verify`.
