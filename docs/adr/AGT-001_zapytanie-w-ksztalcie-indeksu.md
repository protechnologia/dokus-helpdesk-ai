# AGT-001: Zapytanie wektorowe pisze agent, w kształcie indeksu

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-02 |
| Zastępuje | — |
| Zadanie   | zmiana architektury na agenta z narzędziami (commit 543ccc9), narzędzie `find_tickets_vector` (p. 7) |

## Kontekst

Agent sam szuka podobnych zgłoszeń narzędziem `find_tickets_vector`. Wektory kart powstały
z pól `problem` i `symptoms`, które przy imporcie napisał parser korpusu (`parse_ticket`).
Trzeba ustalić, z czego powstaje zapytanie i kto decyduje, ile wyników pobrać i gdzie je uciąć.

## Rozważane opcje

1. Surowy tekst zgłoszenia jako zapytanie — odrzucona: nie ma kształtu pól, z których
   zbudowano wektory.
2. Parser korpusu na nowym zgłoszeniu przed każdym wyszukaniem — odrzucona: wyszukiwanie
   przestaje być decyzją agenta, a przed każdym wyszukaniem dochodzi przebieg modelu.
3. Agent pisze `problem` i `symptoms` sam, a narzędzie przyjmuje tylko te dwa pola — wybrana.

## Decyzja

Opcja 3. Zapytanie ma kształt pól, z których zbudowano wektory, a sparsowanie zgłoszenia pod
wyszukiwanie to zadanie agenta, który może szukać kilka razy innymi słowami. Zapytanie niesie
wyłącznie to, czego szukać: ile pobrać i gdzie uciąć to strojenie (`RAG_TOP_K`,
`RAG_SCORE_MIN` w ENV), nie argument modelu; nieznany argument to błąd walidacji.

## Konsekwencje

### Zyski

- Wyszukiwanie zostaje decyzją agenta, bez stałego kroku parsowania przed nim.
- Próg i liczba wyników są w jednym miejscu, do strojenia bez zmiany promptów.

### Koszty

- Zapytanie nie powstaje tym samym promptem co korpus, więc jego trafność trzeba zmierzyć
  (p. 23). Do tego czasu odniesieniem są zapytania w kształcie narzędzia z golden setu: na kartach
  `gpt-6.1-sol` cel na pierwszym miejscu w 119 ze 126; na kartach Bielika 93,8% wobec 98,1% dla
  zapytań surowych.
