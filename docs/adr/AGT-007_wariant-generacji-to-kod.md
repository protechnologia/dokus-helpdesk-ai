# AGT-007: Wariant generacji to kod: osobny graf na wariant

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-02 |
| Zastępuje | — |
| Zadanie   | commity 543ccc9 (zmiana architektury) i 544a826 (wycofanie wariantów jako danych) |

## Kontekst

Wdrożeniowiec wybiera rodzaj odpowiedzi guzikiem: pytania, rozwiązanie albo przekazanie
sprawy. Do 2026-10-02 warianty były danymi klienta: nazwa, etykieta guzika, prompt
i `requires_hits` w magazynie reguł (`text/variants.json`), więc klient dodawał guzik bez
naszego deployu. Za wariant, który obchodzi zasadę 9 (prompt „wygeneruj rozwiązanie” bez
wymogu trafień), odpowiadał klient: blokada wymagałaby rozumienia, co robi jego prompt, a tego
nie umiemy zrobić niezawodnie.

## Rozważane opcje

1. Warianty jako dane klienta — odrzucona: zasada 9 nie obowiązywałaby wariantów klienta,
   a blokady nie da się zbudować.
2. Osobny graf na wariant w `agent_graphs/suggest_<wariant>`; `/suggest` bierze wariant
   parametrem, a `GET /variants` oddaje listę z rejestru grafów — wybrana.

## Decyzja

Opcja 2. Zasada 9 obowiązuje każdy wariant, bo piszemy je my.

## Konsekwencje

### Zyski

- Każdy wariant ma własne narzędzia, model wyniku i wymóg źródeł (`TOOL_NAMES`,
  `respond_node()`, `REQUIRES_HITS`), a wymóg źródeł egzekwuje kod węzła odpowiedzi.
- Nowy guzik to nowy katalog grafu, bez zmiany routera.
- Znikła druga kopia promptów (`text/prompt_suggest_*` obok katalogów grafów), która groziła
  poprawianiem nie tej (commit 544a826).

### Koszty

- Nowy guzik wymaga deployu.
