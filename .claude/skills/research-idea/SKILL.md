---
name: research-idea
description: >-
  Forked web-research helper for /develop-idea — looks for prior art for one
  project idea (direct equivalents, adjacent projects, community discussion)
  and returns a compact, sourced summary with a verdict. Writes nothing, never
  reads brain/. Called by develop-idea step 7, not meant to be invoked on its
  own.
context: fork
user-invocable: false
allowed-tools: WebSearch WebFetch
---

# research-idea

The prior-art half of `/develop-idea`, split out so that search results and
fetched pages stay in a throwaway context. Only the summary below goes back to
the caller.

You get **no conversation history** — everything you need is in the arguments.

## Input

`$ARGUMENTS`:

```
title: <idea title>
summary: <2–4 sentences: what it is and what problem it solves>
keywords: <comma-separated search keywords>
```

If `keywords` is missing, derive them from `title` and `summary`. If both are
missing, stop and say so.

## Boundaries

- **Web only.** Use WebSearch and WebFetch. Do not read or write any file, and
  do not touch `brain/` — personal context stays with the caller.
- Queries carry only the idea's own keywords — nothing about the owner.
- Paraphrase; never quote verbatim. Cite the source URL for every claim.

## Steps

### 1. Direct equivalents

Search `"<keywords>" existing tool OR project OR app 2025 OR 2026`, then
`<keywords> site:github.com`. WebFetch the most promising 1–3 hits to judge how
close a match each really is.

### 2. Adjacent / community discussion

Search `<keywords> site:reddit.com OR site:news.ycombinator.com self-hosted OR
homelab OR open source`.

### 3. Broaden once

If step 1 returns nothing close, broaden the query once. If prior art is still
sparse or unrelated, **do not** stretch tangential hits into a competitive
landscape. Write plainly: "No close prior art found — likely novel, or too
niche for indexed search coverage."

## Output

Return exactly this, nothing before or after, at most ~50 lines:

```
### Direct equivalents
- **<name>** — <what it does, how close a match> (<URL>)

### Adjacent / inspiration
- **<name>** — <relevance> (<URL>)

### Verdict
<reinvents the wheel, or a genuine gap / personalization angle — one short
paragraph>

Queries used: <list>
```

An empty group is written as `- none found`.
