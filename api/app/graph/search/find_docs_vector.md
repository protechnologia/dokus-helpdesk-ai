<!-- Opis narzędzia `find_docs_vector` w grafie `search` — czyta go MODEL razem ze schematem
     argumentów (`FindDocsVectorQuery` bez docstringów). Szkielet; narzędzie właściwe w p. 8,
     treść opisu stroi się z promptem grafu w p. 23.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka sekcji instrukcji i dokumentacji aplikacji po znaczeniu. Zwraca wiersze spisu treści —
identyfikator sekcji, dokument z wersją, rozdział i krótki opis — bez treści. Treść wybranych
sekcji odczytasz narzędziem `read_docs`.

- `text` — zagadnienie albo słowa kluczowe: nazwa funkcji, ustawienia lub komunikatu.
