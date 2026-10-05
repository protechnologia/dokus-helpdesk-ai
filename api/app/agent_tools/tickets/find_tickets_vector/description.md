<!-- Opis narzędzia `find_tickets_vector` — czyta go MODEL razem ze
     schematem argumentów (`FindTicketsVectorQuery` bez docstringów),
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

Szuka historycznych zgłoszeń podobnych do opisanego problemu w bazie
wektorowej: po znaczeniu, nie słowo w słowo. `problem` i `symptoms`
są łączone i zamieniane na jeden embedding, porównywany z opisem
problemu i symptomów każdego historycznego zgłoszenia.

# Jak wywoływać

| argument | typ   | co podać                            | przykład                                       | opis |
|----------|-------|-------------------------------------|------------------------------------------------|------|
| problem  | tekst | czego dotyczy kłopot                | "Wysyłka przez ePUAP kończy się błędem"        | Jednym-dwoma zdaniami. |
| symptoms | tekst | symptomy widziane przez użytkownika | "Po kliknięciu Wyślij komunikat o braku sieci" | Z komunikatem błędu, jeśli jest. |

Streść zgłoszenie do tych dwóch pól, nie przepisuj go wprost — bez
powitań, podpisów i historii wątku.

# Co zwraca

JSON z samymi numerami zgłoszeń, bez treści:

| pole                    | co zawiera                           |
|-------------------------|--------------------------------------|
| tickets                 | zgłoszenia, od najbardziej podobnego |
| tickets[].ticket_id     | numer zgłoszenia                     |
| tickets[].score         | podobieństwo cosinusowe do zapytania |
| dropped_below_threshold | ile trafień odpadło jako zbyt słabe  |

# Zasady

- Karty, czyli streszczenia zgłoszeń, odczytasz narzędziem
  `read_tickets_card`.
- Oryginalne wątki odczytasz narzędziem `read_tickets_thread`.
- `score` porównuje trafienia w jednym wyniku; nie mówi, czy
  rozwiązanie pasuje.
- Sprawy o tym samym objawie mają tu różne przyczyny, więc przeczytaj
  karty wszystkich zwróconych numerów, nie tylko pierwszego.
- Gdy wszystkie wyniki są słabe albo `dropped_below_threshold` jest
  większe od zera, spróbuj innego opisu.
- Gdy zgłoszenie opisuje kilka różnych objawów, szukaj osobno dla
  każdego.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
