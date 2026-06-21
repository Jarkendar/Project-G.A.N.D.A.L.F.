---
name: init-brain
description: >-
  Initialize or validate the brain/ knowledge repository for G.A.N.D.A.L.F.
  from the skeleton template at .claude/brain-skeleton/. Use this skill for
  first-time setup when brain/ does not exist yet, after cloning this repo on
  a new machine, to validate that an existing brain/ has the correct
  structure, or to recover missing CLAUDE.md/_meta files.
---

# init-brain

Initialize or validate the `brain/` knowledge repository for G.A.N.D.A.L.F.

## When to use

- First-time setup: `brain/` does not exist yet
- After cloning this repo on a new machine
- Validating that an existing `brain/` has the correct structure
- Recovering missing `CLAUDE.md` or `_meta/` files

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

If `$BRAIN` does not exist:
- Tell the user the resolved path and ask: "brain/ not found at `$BRAIN`. Create scaffold?"
- On confirmation: run **Creation mode** (Step 3).
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

---

## Notes

- **Skeleton source.** All file templates live in `.claude/brain-skeleton/` in this
  repo. That directory is the single source of truth for the initial brain structure.
  To add or change a template, edit the file there — not here.
- **No-clobber by design.** Both creation and validation use `-n` / `cp -n`. Existing
  files in brain/ are never overwritten by this skill. This is intentional: living
  documents (core/) accumulate real data and must not be reset.
- **Validation scope.** Validation only checks structural completeness (all skeleton
  files present). It does not verify frontmatter, content, or that living documents
  match the template — they are not supposed to after the first edit.
