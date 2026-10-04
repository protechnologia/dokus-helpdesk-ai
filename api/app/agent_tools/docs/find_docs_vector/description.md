<!-- Opis narzędzia `find_docs_vector` — czyta go MODEL razem ze schematem
     argumentów (`FindDocsVectorQuery` bez docstringów), w każdym grafie, który
     ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje; po co
     wyniki w danej funkcji, mówi prompt grafu. Szkielet; narzędzie właściwe w
     p. 8.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka sekcji instrukcji i dokumentacji aplikacji po znaczeniu. Zwraca opisy
sekcji — identyfikator (`section_id`), dokument z wersją, rozdział, tytuł
i krótki opis — z podobieństwem (`score`), bez treści. Treść wybranych sekcji
odczytasz narzędziem `read_docs`.

- `text` — zagadnienie albo słowa kluczowe: nazwa funkcji, ustawienia lub
  komunikatu.

Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu narzędzie
zwraca błąd zamiast wyniku.
