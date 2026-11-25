# AGT-006: Odpowiedź grafu przychodzi narzędziem `respond_<graf>`

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-02 |
| Zastępuje | — |
| Zadanie   | commity 6d6bb98 (grafy na atrapach) i 27175fd (karta zgłoszenia tą samą drogą) |

## Kontekst

W grafie z pętlą model woła narzędzia wiedzy tak długo, jak potrzebuje; trzeba rozstrzygnąć,
po czym poznać koniec i w jakim kształcie przychodzi wynik. Do 2026-10-02 serwisy wołały model
zwykłym tekstem, a karta zgłoszenia wychodziła JSON-em w tekście, parsowanym do modelu wyniku
z jedną poprawką.

## Rozważane opcje

1. Wynik tekstem (JSON w tekście), a koniec pętli to tura bez wywołań narzędzi — odrzucona:
   koniec rozstrzygałby brak wywołań, a nie to, co model wywołał; format stałby w prompcie
   i w parserze; błąd walidacji wracałby inną drogą niż błędne argumenty narzędzia.
2. Wynik przychodzi wywołaniem narzędzia `respond_<graf>`, którego schemat powstaje z modelu
   wyniku — wybrana.

## Decyzja

Opcja 2. Odpowiedź musi być jedynym wywołaniem w turze. Schemat nie ma `sources`, bo listę
źródeł składa kod z odczytów (zasada 9), a pola, które zna graf (np. numer i data zgłoszenia
w karcie), dokłada graf ze stanu. Karta zgłoszenia przeszła na tę drogę tego samego dnia
(`respond_parse_ticket`); w 6d6bb98 zostawała jeszcze przy JSON-ie w tekście, bo prompt
parsujący jest kontraktem artefaktu.

## Konsekwencje

### Zyski

- Koniec pętli rozstrzyga to, CO model wywołał.
- Format ma jedno źródło: model wyniku.
- Błąd walidacji wraca do modelu tą samą drogą co błędne argumenty narzędzia wiedzy.

### Koszty

- Długi tekst (propozycja, poprawiona notatka) idzie w argumencie wywołania; czy mu to szkodzi,
  mierzą p. 25–28.
- Modele, którym nie da się wymusić wywołania narzędzia (Claude 5.5, serwery zgodne z OpenAI
  przez dostawcę `ollama`), mogą odpowiedzieć samym tekstem i zużyć jedyną poprawkę.
