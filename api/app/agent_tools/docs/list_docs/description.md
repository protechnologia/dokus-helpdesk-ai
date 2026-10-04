<!-- Opis narzędzia `list_docs` — czyta go MODEL razem ze schematem argumentów
     (`ListDocsArgs` bez docstringów), w każdym grafie, który ma to narzędzie na
     liście. Mówi, jak pytać narzędzie i co ono oddaje; po co wyniki w danej
     funkcji, mówi prompt grafu. Szkielet; narzędzie właściwe w p. 51.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Zwraca spis treści dokumentacji aplikacji: opis każdej sekcji — identyfikator
(`section_id`), dokument z wersją, rozdział, tytuł i krótki opis. Nie przyjmuje
argumentów.

Spis mówi, gdzie co jest, a nie co tam stoi. Treść wybranych sekcji odczytasz
narzędziem `read_docs`, podając ich identyfikatory.

Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu narzędzie
zwraca błąd zamiast wyniku.
