# AGT-005: Każda funkcja sama dociąga materiał w swojej pętli

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-02 |
| Zastępuje | — |
| Zadanie   | commit 543ccc9 (zmiana architektury) |

## Kontekst

Propozycja odpowiedzi ma stać na podobnych sprawach i instrukcjach, a przy jednym objawie
przyczyny bywają rozłączne („nic nie przychodzi z e-Doręczeń”: 6 zgłoszeń, 6 przyczyn). Do
2026-10-02 materiał do generacji wybierało jedno wyszukanie: zapytanie z parsera, top-5 po
progu, 1–3 rekordy do promptu. Zaprojektowany, ale niewdrożony był krok człowieka między
wyszukaniem a generacją (decyzja 2026-08-26). Zmiana architektury z 2026-10-02: generuje mocny
model zewnętrzny, a każda funkcja produktu to graf z pętlą agenta i narzędziami.

## Rozważane opcje

1. Trafienia jednego wyszukania idą do promptu wariantu — odrzucona: zapytanie pisze parser,
   wyszukanie jest jedno, a model nie może szukać dalej, gdy materiał nie wystarcza.
2. `/search` raz, człowiek odznacza trafienia, a `/suggest` dostaje ich identyfikatory. Zalety
   zapisane przy tej decyzji: operator wie rzeczy, których system nie wie (urząd nie ma
   eNadawcy, trafienie dotyczy wersji sprzed migracji), odznaczenie jest lepszą etykietą do
   feedbacku niż kliknięcie guzika, a trzy guziki po jednym wyszukaniu to 4 wywołania modelu
   zamiast 6 — odrzucona przy zmianie architektury: materiał wybiera agent, a człowiek w pętli
   przyjdzie później (p. 44).
3. Każda funkcja ma własną pętlę i sama dociąga materiał; `/search` i `/suggest` biorą
   zgłoszenie — wybrana.

## Decyzja

Opcja 3. Agent pisze zapytania sam, może szukać kilka razy i sam ocenia, czy materiał
wystarcza; narzędzia dostaje z listy dozwolonej dla danej funkcji. Źródłem jest to, co
przeczytał (AGT-003).

## Konsekwencje

### Zyski

- Wołający podaje samo zgłoszenie, bez wcześniejszego `/search`.
- Funkcja bez narzędzi wiedzy (bramki, „Popraw”, `handoff`) w ogóle nie szuka.

### Koszty

- Każdy guzik szuka od nowa: ta sama praca jest opłacana dwa razy, a propozycja może stanąć na
  innych sprawach niż te, które operator widział w `/search` (p. 71).
- Człowiek nie odznacza trafień przed generacją, więc ginie etykieta do feedbacku (p. 42).
