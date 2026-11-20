# AGT-003: Wyszukiwanie oddaje identyfikatory, źródłem jest odczyt

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-04 |
| Zastępuje | — |
| Zadanie   | p. 57 (zgłoszenia dwustopniowo, wyniki w JSON-ie) |

## Kontekst

Odpowiedź ma stać na tym, co agent przeczytał, a lista źródeł ma powstawać z wywołań narzędzi,
nie z deklaracji modelu (zasada 9). Dokumentacja szła już prawie dwustopniowo (szukanie
tekstowe oddawało jeszcze fragment treści), a wyszukiwanie zgłoszeń oddawało trafienia razem
z treścią i `score`. W korpusie sprawy o tym samym objawie mają różne przyczyny („nic nie
przychodzi z e-Doręczeń”: 6 zgłoszeń, 6 przyczyn).

## Rozważane opcje

1. Wyszukiwanie oddaje trafienia z treścią i jest źródłem — odrzucona: źródłem byłoby to, co
   model znalazł, a nie to, co przeczytał.
2. Wyszukiwanie oddaje identyfikatory z dopasowanym fragmentem albo z `problem` karty, a treść
   daje odczyt — odrzucona: fragment mógłby modelowi wystarczyć zamiast odczytu, a odpowiedź
   niosłaby wtedy treść bez źródła; wiersz z objawem zachęca do przeczytania jednej karty.
3. Wyszukiwanie oddaje same identyfikatory (zgłoszenie: numer z `score` albo sposobem
   dopasowania; sekcja dokumentacji: opis z metryczki), a treść dają odczyty i tylko one cytują
   — wybrana.

## Decyzja

Opcja 3. Źródłem jest to, co model przeczytał. Przy gołych numerach model nie ma po czym
wybierać i czyta wszystkie karty, czyli także te z konkurującą przyczyną. Opis sekcji
dokumentacji zostaje, bo mówi, o czym sekcja jest, a nie co w niej stoi.

## Konsekwencje

### Zyski

- Wariant wymagający źródeł wymusza przeczytanie materiału, a nie samo jego znalezienie.
- Karty o jednym objawie i różnych przyczynach trafiają do modelu razem.

### Koszty

- Jedna tura modelu więcej na każde wyszukanie.
- `score` znika ze źródeł i z odpowiedzi API: widzi go tylko model, do decyzji, czy szukać
  dalej; nie jest miarą trafności rozwiązania.
- Kod aplikacji idzie inaczej: szukanie w kodzie oddaje treść linii, a źródłem jest dopiero
  fragment zacytowany jako przyczyna (AGT-004).
