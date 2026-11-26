# CLAUDE.md — core/health/labs/

## Purpose
The owner's medical examinations: one transcription per examination
(`reports/`) and the interpretations beside this file. The rows of tabular
results are in `db/labs.db`, each report pointing to its transcription.

## Privacy level
**PRIVATE.** MVP exception: the Claude-API engine may see it —
IMPLEMENTATION.md § "Privacy in the Claude-API MVP".

## Files
| File | Writer |
|---|---|
| `reports/<exam date>_<provider>[_n].md` | `ioreth` MCP server (`save`), after the owner's yes |
| `<exam date>_interpretation[_n].md` | I.O.R.E.T.H., after the owner's yes |

## Source of an examination
Kept so the original can be asked for from the provider: provider, collection
point, order / exam / document numbers with their printed labels, examination
date, result date. A missing one is written `brak`, an unreadable one
`[nieczytelne]`.

## Not stored
Originals (PDF, images). PESEL, address, name and anything else identifying the
owner (`[pominięto]`). Portal access codes and passwords.

## Rules
- Nothing is deleted or edited: a correction is a new report naming the old one
  in `supersedes:`.
- A transcription is a model's reading of a document, checked by the owner; the
  provider's original is the authority.
- Interpretations are not medical assessments.
