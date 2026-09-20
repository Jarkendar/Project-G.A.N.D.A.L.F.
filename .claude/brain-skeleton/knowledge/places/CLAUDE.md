# CLAUDE.md — knowledge/places/

Notatki o odwiedzonych miejscach: restauracje, bary, kawiarnie, lokale,
atrakcje turystyczne, lotniska, obiekty sportowe, miasta. Jedno miejsce = jeden plik.
Dla wydarzeń odbywających się w danym miejscu → `knowledge/events/`.

## Nazewnictwo plików

Żywe dokumenty (miejsce odwiedzane wielokrotnie): `slug.md`
Slug = kebab-case, ≤40 znaków, bez polskich znaków (ą→a, ę→e, ó→o itd.).
Forma: `<nazwa>-<miasto>.md` (np. `bistro-pod-lipami-krakow.md`, `rynek-glowny-krakow.md`).

## Schemat frontmattera

Wymagane (brain/ schema): `date`, `source`, `privacy`, `tags`
Dodatkowe dla miejsc:

```yaml
type: restaurant | bar | cafe | venue | attraction | city | aerodrome | other
city: Kraków
address: ul. Przykładowa 1, Kraków      # opcjonalne
cuisine: Polish                           # tylko dla gastronomii
visited:
  - YYYY-MM-DD (z kim, przy jakiej okazji)
tags: [places, <type>, <city-slug>]
title: "<Nazwa> — <Miasto>"
```

## Skala ocen

Używana w tabeli wizyt (kolumna "Ocena"):

| Gwiazdki | Opisowo |
|---|---|
| ★★★★★ | świetne |
| ★★★★☆ | dobre |
| ★★★☆☆ | przeciętne |
| ★★☆☆☆ | słabe |
| ★☆☆☆☆ | odradzam |

## Struktura body

```markdown
# <Nazwa> — <Miasto>

Jeden zdanie opisu (typ miejsca, lokalizacja).

## Ogólna ocena
Krótkie zdanie lub dwa — charakter miejsca, dla kogo polecane.

## Wizyty
| Data | Okazja | Ocena | Notatki |
|---|---|---|---|
| YYYY-MM-DD | ... | ★★★★★ | ... |
```

Jeśli miejsce było tłem eventu, dodaj wiersz w tabeli z linkiem:
`| 2026-06-21 | [Bieg uliczny](../events/2026-06-21_bieg-uliczny-krakow.md) | ★★★★☆ | ... |`

## Privacy
Domyślnie `private` — dane osobowe (z kim byłem). Zmień na `public` tylko
dla obiektywnych opisów bez danych osobowych.
