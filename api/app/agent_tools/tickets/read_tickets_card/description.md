<!-- Opis narzędzia `read_tickets_card` — czyta go MODEL razem ze schematem
     argumentów (`ReadTicketsCardQuery` bez docstringów), w każdym grafie, który
     ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje; po co
     wyniki w danej funkcji, mówi prompt grafu.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Odczytuje karty zgłoszeń po numerach z wyszukiwania. Karta to streszczenie
sprawy w polach `problem`, `symptoms`, `cause`, `solution` i kilku pomocniczych.
Dosłownych sformułowań klienta i części szczegółów może w karcie nie być, a
`brak` w polu znaczy, że tego nie ustalono.

- `ticket_ids` — od jednego do dwudziestu numerów zgłoszeń, dokładnie w
  brzmieniu z pola `ticket_id`.

Przeczytaj karty WSZYSTKICH znalezionych zgłoszeń, nie tylko pierwszego: sprawy
o tym samym objawie mają tu różne przyczyny, a widać to dopiero w kartach.

Numery w `without_card` to zgłoszenia bez karty — ich treść da tylko
`read_tickets_thread`. Odczytana karta trafia na listę źródeł odpowiedzi.
