# CLAUDE.md — knowledge/events/

Notatki o konkretnych wydarzeniach: koncerty, festiwale, imprezy lotnicze,
wycieczki, spływy, zawody sportowe, eventy kulturalne. Jedno wydarzenie = jeden plik.
Miejsce eventu dostaje równolegle wpis w `knowledge/places/`.

## Nazewnictwo plików

`YYYY-MM-DD_<slug>.md` — data startu eventu na początku (ułatwia bocie orientację
w czasie, sortuje chronologicznie).
Slug = kebab-case, ≤40 znaków, bez polskich znaków.
Przykłady: `2026-06-21_bieg-uliczny-krakow.md`, `2025-08-15_splyw-kajakowy.md`

Dla wielodniowych eventów: data pierwszego dnia w nazwie; `date_end` w frontmatterze.

## Schemat frontmattera

Wymagane (brain/ schema): `date`, `source`, `privacy`, `tags`
Dodatkowe dla eventów:

```yaml
type: event
event_type: race | concert | festival | airshow | kayak | trip | sports | cultural | other
date_start: YYYY-MM-DD
date_end: YYYY-MM-DD          # pomiń jeśli jednodniowe
city: Kraków
venue: knowledge/places/<slug>.md   # opcjonalny pointer do pliku miejsca
with: [Anna, Jan]                   # osoby towarzyszące
travel: pieszo | rowerem | samochodem | pociągiem | samolotem | ...
accommodation: dom | hotel/<nazwa> | namiot | brak    # pomiń jeśli nie nocował
tags: [events, <event_type>, <city-slug>, <YYYY>]
title: "<Nazwa eventu> — <Miasto/Rok>"
```

## Struktura body

Sekcje są opcjonalne — wpisuj tylko te, które mają treść.

```markdown
# <Nazwa> — <Miasto/Rok>

Jedno zdanie streszczenia (co, kiedy, gdzie).

## Wydarzenie
Fakty: program, wyniki, co się działo.

## Jak dotarłem
Środek transportu, trasa, czas przejazdu — jeśli warte odnotowania.

## Nocleg
Gdzie spałem, ocena — tylko przy wyjazdach.

## Koszty
Szacunkowa suma wydatków (nocleg, transport, jedzenie, atrakcje/bilety) —
tylko przy wyjazdach/wycieczkach, nie przy jednodniowych eventach (biegi,
koncerty). Orientacyjnie "ile mniej więcej wydałem/wydaliśmy", nie rozliczenie
z paragonów — cel to punkt odniesienia do szacowania kosztu przyszłych
podobnych wyjazdów, nie księgowość.

## Wrażenia
Subiektywne odczucia, atmosfera, co zapamiętałem, z kim byłem.

## Highlights
Kilka punktorów — najważniejsze momenty lub fakty do zapamiętania.
```

## Privacy
Domyślnie `private` — zawiera dane osobowe i prywatne odczucia.
