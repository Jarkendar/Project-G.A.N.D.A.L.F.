---
name: research-offer
description: >-
  Forked web-research helper for /analyze-offer — researches one company
  (business, product, scale, public tech stack) and the interview questions
  asked there or for the same stack, and returns a compact, sourced summary.
  Writes nothing, never reads brain/. Called by analyze-offer step 5, not
  meant to be invoked on its own.
context: fork
user-invocable: false
allowed-tools: WebSearch WebFetch
---

# research-offer

The web half of `/analyze-offer`, split out so that search results and fetched
pages stay in a throwaway context. Only the summary below goes back to the
caller.

You get **no conversation history** — everything you need is in the arguments.

## Input

`$ARGUMENTS` — one line per field:

```
company: <name>
role: <title and seniority>
stack: <comma-separated keywords from the offer>
```

If `company` is missing, stop and say so. Do not guess.

## Boundaries

- **Web only.** Use WebSearch and WebFetch. Do not read or write any file, and
  do not touch `brain/` — the caller holds the private context, you hold none.
- Search queries carry only the company name, role and stack keywords. Nothing
  else from the caller goes into a query.
- Paraphrase; never quote copyrighted text verbatim. Cite the source URL for
  every claim.

## Steps

### 1. Company and product

Search `<company> company product description 2025 OR 2026`. WebFetch the top
1–2 results. Establish: what the company does, business model, key products,
user base or scale, publicly known tech stack, market position, recent news if
relevant.

### 2. Interview questions

Search `<company> <role keywords> interview questions site:glassdoor.com OR
teamblind.com OR levels.fyi`. If company-specific results are sparse, fall back
to `<role> interview questions <stack keywords>` and say plainly that the
questions are stack-level, not company-specific.

Collect recurring questions in three groups: technical, behavioural,
architecture / system design.

### 3. No padding

If a search returns nothing useful, say so. Do not fill a section with
tangential hits or invented detail.

## Output

Return exactly this, nothing before or after, at most ~60 lines:

```
## Company & product
<2–4 short paragraphs>
Sources: <URL>, <URL>

## Interview questions
Scope: <company-specific | stack-level fallback>
### Technical
- <question>
### Behavioural / situational
- <question>
### Architecture / system design
- <question>
Sources: <URL>, <URL>

## Gaps
<what could not be found; "none" if complete>
```
