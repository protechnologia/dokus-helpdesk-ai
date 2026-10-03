<!-- Opis narzędzia `list_docs` w grafie `suggest_solution` — czyta go MODEL razem ze schematem
     argumentów (`ListDocsArgs` bez docstringów). Szkielet; narzędzie właściwe w p. 51,
     treść opisu stroi się z promptem grafu w p. 26.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Zwraca spis treści dokumentacji aplikacji: po wierszu na sekcję — identyfikator w nawiasie
kwadratowym, dokument z wersją, rozdział i krótki opis. Nie przyjmuje argumentów.

Spis mówi, gdzie co jest, a nie co tam stoi. Treść wybranych sekcji odczytasz narzędziem
`read_docs`, podając ich identyfikatory.
