<!-- Opis narzędzia `read_tickets_thread` — czyta go MODEL razem ze schematem
     argumentów (`ReadTicketsThreadQuery` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje;
     po co wyniki w danej funkcji, mówi prompt grafu. Szkielet; narzędzie
     właściwe w p. 56.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Odczytuje oryginalne wątki zgłoszeń po numerach z wyszukiwania: temat, opis
zgłaszającego i komentarze, w brzmieniu, w jakim je napisano. Sięgnij po wątek,
gdy karta nie niesie szczegółu, którego potrzebujesz — dosłownego komunikatu,
kolejności zdarzeń, tego, kto co zrobił — albo gdy zgłoszenie nie ma karty.

- `ticket_ids` — od jednego do pięciu numerów zgłoszeń, dokładnie w brzmieniu
  z pola `ticket_id`. Nieznany numer kończy się błędem, bez wyniku częściowego.

Wątki są długie: czytaj te, które wybrałeś po kartach, nie wszystkie znalezione.
Odczytany wątek trafia na listę źródeł odpowiedzi.

Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu narzędzie
zwraca błąd zamiast wyniku.
