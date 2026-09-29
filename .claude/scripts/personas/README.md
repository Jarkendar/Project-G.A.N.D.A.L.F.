# Persona build scripts

Helpers for building a White Council persona card (IMPLEMENTATION.md, Step 6,
"Building a persona"). The digests themselves are written by Claude from the
source text; these scripts do the mechanical parts around them: preparing
the text for reading, checking quotes, and adding frontmatter.

Every script takes the persona slug first and resolves `brain/` from
`BRAIN_PATH` in `.claude/gandalf.env`.

## Where the data lives

| What | Where | In git |
|---|---|---|
| Card, catalogue, digests | `brain/knowledge/personas/<slug>/` | yes (brain) |
| Source rows (`catalog.json`) | `~/.local/share/gandalf/personas/<slug>/` | no |
| Originals as fetched | `…/<slug>/originals/` | no |
| Plain text (`<id>.txt`) | `…/<slug>/text/` | no |

`catalog.json` holds one row per source: `id`, `url`, `wayback`, `sha256`,
`words`, and — once the source is digested — `file`, `title`,
`source_type`, `source_date` and `tags` (fixed tags placed after
`persona, <slug>`). The cache is reproducible from `sources.md` (URL or
Wayback, then a `sha256` check); it is not backed up.

## Scripts

| Script | Step | What it does |
|---|---|---|
| `reflow.py <slug> <id>` | 3 | Prints the source text one paragraph per line, tables squeezed to one `[TABLE]` line — the reading input for a digest. |
| `assemble.py <slug> <drafts> <id,...> [--write]` | 3 → 3b | Checks draft quotes; with `--write` adds frontmatter from the catalogue row, writes `sources/<file>` and flips `todo` → `esencja` in `sources.md`. |
| `verify_quotes.py <slug> [id ...]` | 3b | Checks every `> ` quote in finished digests against the source text; exit 1 on a miss. No ids = all digests. |

A draft (`<drafts>/<id>.md`) is the digest body preceded by one line of
topic tags and a separator:

```
tags: [topic-a, topic-b]
---

# <title>
...
```

Quote matching normalises quotes, dashes, soft hyphens and whitespace, and
ignores case; a quote elided with `...` passes when each fragment appears in
the source.
