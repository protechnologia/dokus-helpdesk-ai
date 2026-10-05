<!-- Opis narzędzia `read_tickets_thread` — czyta go MODEL razem ze
     schematem argumentów (`ReadTicketsThreadQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu. Szkielet; narzędzie właściwe w p. 56.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty i pola wyniku w tabelkach, linie do 70 znaków —
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Odczytuje oryginalne wątki zgłoszeń po numerach z wyszukiwania.
Sięgnij po wątek, gdy karta, czyli streszczenie zgłoszenia, nie
niesie szczegółu, którego potrzebujesz — dosłownego komunikatu,
kolejności zdarzeń, tego, kto co zrobił — albo gdy zgłoszenie nie
ma karty.

# Jak wywoływać

| argument   | typ           | co podać        | przykład           | opis |
|------------|---------------|-----------------|--------------------|------|
| ticket_ids | lista tekstów | numery zgłoszeń | ["90011", "90012"] | Od jednego do pięciu numerów, dokładnie w brzmieniu z pola `ticket_id`. Nieznany numer kończy się błędem, bez wyniku częściowego. |

# Co zwraca

JSON:

| pole                | co zawiera        |
|---------------------|-------------------|
| threads             | odczytane wątki   |
| threads[].ticket_id | numer zgłoszenia  |
| threads[].date      | data zgłoszenia   |
| threads[].subject   | temat zgłoszenia  |
| threads[].thread    | pełny tekst wątku |

Tekst wątku to temat, opis zgłaszającego i komentarze, w brzmieniu,
w jakim je napisano.

# Zasady

- Wątki są długie: czytaj te, które wybrałeś po kartach, nie
  wszystkie znalezione.
- Odczytany wątek trafia na listę źródeł odpowiedzi.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
