# AGT-004: Źródłem z kodu jest fragment zacytowany jako przyczyna

| pole      | wartość |
|-----------|---------|
| Status    | Przyjęta 2026-10-06 (narzędzie `quote_code` 2026-10-07) |
| Zastępuje | — |
| Zadanie   | p. 60–67 (narzędzia kodu aplikacji), p. 67 (`quote_code`) |

## Kontekst

Narzędzia kodu aplikacji mają pomóc tam, gdzie zgłoszenia i instrukcje nic nie dają, przede
wszystkim przy komunikacie albo kodzie błędu. Model przechodzi przez dużo więcej plików, niż
potrzebuje do odpowiedzi. Wariant `solution` bez źródeł nie oddaje propozycji, więc od tego, co
w kodzie jest źródłem, zależy, czy odpowiedź oparta na samym kodzie w ogóle może powstać.

## Rozważane opcje

1. Kod nie jest źródłem albo odpowiedź oparta tylko na kodzie jest blokowana — odrzucona:
   zatrzymałaby sprawy bez podobnych zgłoszeń i instrukcji, czyli te, dla których narzędzia kodu
   powstały. Wraca w węższej postaci (źródłem tylko plik znaleziony dosłownym trafieniem), gdy
   pomiar pokaże odpowiedzi z luźno powiązanych plików (p. 59).
2. Każdy odczytany plik jest źródłem, jak odczyt karty zgłoszenia — odrzucona: plik zawsze da się
   przeczytać, więc wariant prawie nigdy nie powiedziałby „nie mam z czego zaproponować”.
3. Cytowanie, które oddaje modelowi treść cytowanych linii — odrzucona: w sondzie model cytował
   zamiast czytać.
4. Osobne narzędzie `quote_code`: jeden fragment na wywołanie, z rolą `cause` (powoduje opisane
   zachowanie) albo `excluded` (sprawdzony i wykluczony); źródłem jest tylko `cause`, a model
   dostaje samo potwierdzenie — wybrana.

## Decyzja

Opcja 4. Kod liczy się jako źródło na równi ze zgłoszeniem i instrukcją, także w wariancie
wymagającym źródeł, ale źródłem jest wskazana przyczyna, nie przeczytany plik.

## Konsekwencje

### Zyski

- Odpowiedź oparta tylko na kodzie jest możliwa i rozpoznawalna po źródłach rodzaju `code`.
- Szukanie i odczyt w kodzie są narzędziami pomocniczymi, więc szukanie może oddać treść
  trafionej linii; bez niej model nie odróżni definicji od setek użyć tej samej nazwy
  („raiseError” stoi w 550 liniach w 197 plikach).

### Koszty

- Narzędzie nie widzi rozmowy i nie sprawdza, czy model cytowane linie czytał: regułę niesie
  opis dla modelu, a liczy pomiar (p. 59). Model może też wskazać przyczynę po jednej linii,
  której otoczenia nie czytał.
- Wykluczenie źródłem nie jest; do człowieka trafia przez uwagi dla wdrożeniowca i `queries`
  w odpowiedzi `/search`.
