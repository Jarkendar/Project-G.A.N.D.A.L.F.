# CLAUDE.md — knowledge/travel/

Wiedza o podróżowaniu jako takim — rzeczy przenośne między wyjazdami: katalog
rzeczy do pakowania, typy wyjazdów, wyciągnięte wnioski logistyczne.

**To nie jest miejsce na konkretne wyjazdy.** Odbyty wyjazd → `knowledge/events/`.
Odwiedzone miejsce → `knowledge/places/`. Lista pakowania na konkretny wyjazd →
`current/trips/` (prywatna, generowana przez `/pack`).

## Struktura

```
travel/
  packing/
    catalogue.md     # pula rzeczy: priorytet + warunki + grupa + scope
    trip-types.md    # presety wyjazdów → zestawy warunków
```

## Privacy

**PUBLIC** — katalog jest generyczny i bezosobowy. Rzeczy specyficzne dla osoby
(leki, soczewki, kosmetyki, rozmiary, co kto posiada) należą do
`core/travel/packing/<slug>.md` i są **PRIVATE**. Nigdy nie przenoś treści
z profilu osoby do katalogu.

## Katalog ≠ inwentarz

Pozycja w `catalogue.md` znaczy „to bywa potrzebne na wyjeździe", a nie
„ktoś to ma". Posiadanie jest per osoba, w profilu, w sekcji `Posiada`.
Stara lista pakowania z konkretnego wyjazdu nie jest źródłem wiedzy
o posiadaniu ani o stałych nawykach.

## Writers

| Source | Allowed | Conditions |
|---|---|---|
| User (manual) | ✅ | Dowolny plik |
| `/pack` skill | ✅ | Za potwierdzeniem użytkownika |
| Inne agenty | ❌ | Read-only |

## Wymagany frontmatter

```yaml
date: <ISO 8601>
source: pack | manual
privacy: public
status: active
tags: [travel, packing, ...]
```

## Not allowed

- Usuwanie pozycji z katalogu — rzeczy nieużywane degraduje się priorytetem
  (`must` → `base` → `extra`) albo zawęża warunkiem, nie kasuje.
- Dane osobowe, zdrowotne i medyczne — te idą do `core/`.
