# RB-001: Odchudzanie podsekcji CLAUDE.md

## Cel

Jedna podsekcja CLAUDE.md krótsza, bez utraty faktów: duże decyzje stoją w ADR, procedury
w runbookach, wypada to, co łatwo wyciągnąć z kodu, a każdy punkt ma jeden układ.

## Kiedy

Co jakiś czas, jedna podsekcja naraz.

## Wymaga

- `.venv` z `requirements-dev.txt`, do testów linków do ADR i runbooków.

## Kroki

Podsekcję wybieramy razem: agent proponuje kandydatów z rozmiarem (linie, znaki), szacunkiem,
ile da się wyciągnąć z kodu, oraz kandydatami na ADR i runbook, a wybiera użytkownik.

Każdy krok to plik do przeglądu w scratchpadzie, podany pełną ścieżką, z decyzją i powodem przy
każdym punkcie; zmiana dopiero po „ok” użytkownika i osobnym commitem na krok. Po każdym kroku
skrypt porównuje liczby, daty i odesłania do planu („p. N”) obu wersji, a różnicę wymienia opis
commita.

1. **ADR** — duże decyzje podsekcji do ADR (decyzja, opcje, powód) według zasad
   z `docs/adr/README.md`. Powód tylko z zapisów: gdy go w nich nie ma, pominąć albo zapytać,
   bez domysłów. W podsekcji zostaje reguła, to, co z niej wynika, i link.
2. **Runbook** — procedury z podsekcji, których kod nie zapisuje, idą do `docs/runbook/` (kroki,
   dostępy, koszt, sprzątanie); w CLAUDE.md zostaje reguła i link. Procedura operatora instancji
   należy do README, a dopóki go nie ma, zostaje w CLAUDE.md.
3. **Czyszczenie** — wypada to, co się nie przyda albo łatwo wyciągnąć z kodu; przy „bo jest
   w kodzie” sprawdzamy, że to naprawdę stoi w docstringu, modelu albo opisie narzędzia. Zdanie,
   które ma zostać, a nie ma odpowiednika w kodzie, przechodzi do komentarza przy kodzie, którego
   dotyczy; w prompcie i opisie narzędzia to komentarz redakcyjny (`<!-- … -->`), wycinany przed
   wysłaniem.
4. **Łączenie** — punkty o jednej osi w jeden, ułożone tematycznie, bez przepisywania słów:
   dochodzą najwyżej spójniki, a powtórzony podmiot wypada.
5. **Zwięzłość** — każdy punkt w jednym układzie: pogrubiona decyzja z datą, dlaczego, liczby,
   na końcu „Cena:” albo otwarte pytanie; fakty bez zmian. Plik do przeglądu ma przy każdym
   punkcie wersję „przed” i „po”.

## Weryfikacja

- Skrypt porównujący: liczby, daty i odesłania do planu są w obu wersjach te same albo różnica
  stoi w opisie commita.
- `pytest tests/integration/test_docs_adr_links.py tests/integration/test_docs_runbook_links.py`
  zielony.
- Opis commita: krok, linie i znaki podsekcji przed i po, co wypadło i gdzie to teraz stoi.

## Pułapki

- Skrypt porównujący pisze się dziś od nowa w scratchpadzie przy każdym kroku; to kandydat na
  skrypt w `scripts/`.
- Komentarz redakcyjny w prompcie parsującym nie może zmienić skrótu promptu, który zapisuje
  raport importu korpusu: sprawdzić skrót przed i po.
- Sekcje CLAUDE.md nie odwołują się do siebie nawzajem, więc punkt przeniesiony do ADR albo
  runbooka nie zostawia po sobie „patrz wyżej”.

## Powiązania

- [CLAUDE.md, „Dokumentacja” → „CLAUDE.md”](../../CLAUDE.md#claudemd): reguła odchudzania;
  [„ADR”](../../CLAUDE.md#adr) i [„Runbook”](../../CLAUDE.md#runbook): dokąd przechodzą decyzje
  i procedury.
- [Zasady ADR](../adr/README.md) (krok 1) i [zasady runbooków](README.md) (krok 2).
- [`test_docs_adr_links.py`](../../tests/integration/test_docs_adr_links.py)
  i [`test_docs_runbook_links.py`](../../tests/integration/test_docs_runbook_links.py): linki
  do ADR i runbooków po przeniesieniu.

## Log

Najnowszy wpis na górze.

- 2026-11-25 — „Warstwa grafów”: 210 → 88 linii, ADR-006–009 (wtedy AGT-005–008), cztery kroki przyjęte bez
  poprawek; bez kroku 2 (runbook), który doszedł tego dnia. Do runbooka doszło: domysłów powodu
  nie wpisywać do ADR, zdanie bez odpowiednika w kodzie przenieść do komentarza redakcyjnego.
- 2026-11-20 — „Warstwa narzędzi agenta”: 271 → 97 linii, potem ADR-y do 84. ADR-y powstały
  dopiero po trzech przejściach, stąd ADR jako krok pierwszy.
- 2026-11-11 — „Świadomie pominięte”: 579 → 151 linii; plik z decyzją i powodem przy każdym
  punkcie i szkic zwięzłości „przed” i „po” przyjęte bez poprawek.
