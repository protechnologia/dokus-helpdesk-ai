<!-- Opis narzędzia `read_tickets_card` — czyta go MODEL razem ze
     schematem argumentów (`ReadTicketsCardQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Miejsce `{{resolution_classes}}` wypełnia narzędzie klasami ze
     słownika klienta (`dict_resolution.json`): po punkcie na klasę,
     nazwa i jej znaczenie. Znaczeń nie wpisujemy tu ręcznie.

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

| pole                      | co zawiera                             |
|---------------------------|----------------------------------------|
| cards                     | karty odczytanych zgłoszeń             |
| cards[].ticket_id         | numer zgłoszenia                       |
| cards[].date              | data zgłoszenia                        |
| cards[].component         | aplikacja albo usługa, której dotyczy  |
| cards[].problem           | zwięzły opis problemu                  |
| cards[].symptoms          | objawy widziane przez użytkownika      |
| cards[].error_codes       | kody błędów i sygnatury                |
| cards[].cause             | ustalona przyczyna                     |
| cards[].solution          | co rozwiązało sprawę, z zastrzeżeniami |
| cards[].resolution        | klasa rozstrzygnięcia, opisana niżej   |
| cards[].questions_summary | o co dopytywał prowadzący sprawę       |
| without_card              | numery zgłoszeń, które nie mają karty  |

Klasy rozstrzygnięcia (`resolution`):

{{resolution_classes}}

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
