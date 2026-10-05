<!-- Opis narzędzia `read_tickets_thread` — czyta go MODEL razem ze
     schematem argumentów (`ReadTicketsThreadQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Odczytuje oryginalny wątek zgłoszenia po numerze z wyszukiwania.
Sięgnij po wątek, gdy karta, czyli streszczenie zgłoszenia, nie
niesie szczegółu, którego potrzebujesz — dosłownego komunikatu,
kolejności zdarzeń, tego, kto co zrobił — albo gdy zgłoszenie nie
ma karty.

# Jak wywoływać

| argument  | typ   | co podać         | przykład | opis |
|-----------|-------|------------------|----------|------|
| ticket_id | tekst | numer zgłoszenia | "90011"  | Jeden numer, dokładnie w brzmieniu z pola `ticket_id`. Nieznany numer kończy się błędem. |

# Co zwraca

JSON z jednym wątkiem:

| pole      | co zawiera        |
|-----------|-------------------|
| ticket_id | numer zgłoszenia  |
| date      | data zgłoszenia   |
| subject   | temat zgłoszenia  |
| thread    | pełny tekst wątku |

Tekst wątku to temat, opis zgłaszającego i komentarze, w brzmieniu,
w jakim je napisano.

# Zasady

- Jedno wywołanie to jeden wątek. Kolejny wątek odczytaj osobnym
  wywołaniem; limit wywołań jest więc limitem wątków.
- Wątki są długie: czytaj te, które wybrałeś po kartach, nie
  wszystkie znalezione.
- Odczytany wątek trafia na listę źródeł odpowiedzi.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
