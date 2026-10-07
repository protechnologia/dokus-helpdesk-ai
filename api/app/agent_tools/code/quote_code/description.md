<!-- Opis narzędzia `quote_code` — czyta go MODEL razem ze schematem
     argumentów (`QuoteCodeQuery` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co
     ono oddaje; po co wyniki w danej funkcji, mówi prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Liczba 40 w tabelce argumentów to `MAX_LINES_PER_QUOTE` z
     `models.py`; pilnuje jej test opisu.

     Zasady nie wymieniają jeszcze narzędzi odczytu kodu po nazwie:
     dojdą razem z nimi (p. 63, 66).

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Mówi człowiekowi, który dostaje odpowiedź, na podstawie którego
fragmentu kodu aplikacji ją dałeś: fragment zacytowany jako
przyczyna (rola `cause`) trafia na listę źródeł odpowiedzi. To ta
sama lista, na którą trafiają zgłoszenia i sekcje dokumentacji,
które przeczytałeś. Tym samym narzędziem oznaczasz miejsce, które
sprawdziłeś i wykluczyłeś (rola `excluded`) — ono źródłem nie
jest.

# Jak wywoływać

| argument  | typ    | co podać                 | przykład                                      | opis |
|-----------|--------|--------------------------|-----------------------------------------------|------|
| path      | tekst  | ścieżka pliku            | "src/lib/Urzad/Numeracja/GeneratorNumeru.php" | Ścieżka pliku w kodzie aplikacji, względem jego katalogu głównego. Ścieżka spoza kodu, katalog albo plik, którego nie ma, kończy się błędem. |
| from_line | liczba | pierwsza linia fragmentu | 17                                            | Numer linii w pliku, liczony od 1. |
| to_line   | liczba | ostatnia linia fragmentu | 19                                            | Nie mniejszy niż `from_line`. Fragment ma najwyżej 40 linii; linia spoza pliku kończy się błędem. |
| role      | tekst  | rola cytowania           | "cause"                                       | `cause`: ten fragment powoduje zachowanie opisane w zgłoszeniu. `excluded`: fragment sprawdzony i wykluczony jako przyczyna. |

# Co zwraca

JSON z potwierdzeniem cytowania, bez treści linii:

| pole      | co zawiera                       |
|-----------|----------------------------------|
| path      | ścieżka pliku w kodzie aplikacji |
| from_line | pierwsza linia fragmentu         |
| to_line   | ostatnia linia fragmentu         |
| role      | rola, w której fragment zapisano |

# Zasady

- Tylko cytowanie z rolą `cause` trafia na listę źródeł odpowiedzi.
  Cytowanie `excluded` źródłem nie jest.
- Roli `cause` użyj tylko wtedy, gdy przeczytany kod pokazuje, że
  fragment powoduje opisane zachowanie. Gdy kod przyczyny nie
  pokazuje, nie cytuj niczego jako `cause`.
- Cytuj wyłącznie linie, które wcześniej przeczytałeś. To narzędzie
  nie pokazuje kodu, więc odczytu nie zastąpi.
- Jedno wywołanie to jeden fragment. Cytuj samo miejsce, które
  rozstrzyga: warunek, ustawienie, treść komunikatu.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
