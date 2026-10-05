<!-- Opis narzędzia `read_tickets_card` — czyta go MODEL razem ze
     schematem argumentów (`ReadTicketsCardQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty i pola wyniku w tabelkach, linie do 70 znaków —
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Odczytuje karty zgłoszeń po numerach z wyszukiwania. Karta to
streszczenie sprawy.

# Jak wywoływać

| argument   | typ           | co podać        | przykład           | opis |
|------------|---------------|-----------------|--------------------|------|
| ticket_ids | lista tekstów | numery zgłoszeń | ["90001", "90003"] | Od jednego do dwudziestu numerów, dokładnie w brzmieniu z pola `ticket_id`. |

# Co zwraca

JSON:

| pole         | co zawiera                            |
|--------------|---------------------------------------|
| cards        | karty odczytanych zgłoszeń            |
| without_card | numery zgłoszeń, które nie mają karty |

Pola karty:

| pole              | co zawiera                                  |
|-------------------|---------------------------------------------|
| ticket_id         | numer zgłoszenia                            |
| date              | data zgłoszenia                             |
| component         | czego dotyczy: aplikacja, usługa zewnętrzna |
| problem           | zwięzły opis problemu                       |
| symptoms          | objawy widziane przez użytkownika           |
| error_codes       | kody błędów i sygnatury                     |
| cause             | ustalona przyczyna                          |
| solution          | co rozwiązało sprawę, z zastrzeżeniami      |
| resolution        | klasa rozstrzygnięcia                       |
| questions_summary | o co dopytywał prowadzący sprawę            |

# Zasady

- Przeczytaj karty WSZYSTKICH znalezionych zgłoszeń, nie tylko
  pierwszego: sprawy o tym samym objawie mają tu różne przyczyny,
  a widać to dopiero w kartach.
- Dosłownych sformułowań klienta i części szczegółów może w karcie
  nie być, a `brak` w polu znaczy, że tego nie ustalono.
- Treść zgłoszeń z `without_card` da tylko `read_tickets_thread`.
- Odczytana karta trafia na listę źródeł odpowiedzi.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
