<!-- Opis narzędzia `find_docs_text` — czyta go MODEL razem ze schematem
     argumentów (`FindDocsTextQuery` bez docstringów), w każdym grafie, który ma
     to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje; po co
     wyniki w danej funkcji, mówi prompt grafu. Szkielet; narzędzie właściwe w
     p. 50.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka sekcji dokumentacji aplikacji po dosłownym brzmieniu, nie po znaczeniu.
Zwraca opisy sekcji — identyfikator (`section_id`), dokument z wersją, rozdział,
tytuł i krótki opis — z informacją, czym każdą znaleziono (`matched_by`: `exact`
albo `words`), bez treści. Treść wybranych sekcji odczytasz narzędziem
`read_docs`.

- `exact` — dosłowne ciągi: nazwa opcji lub przycisku, komunikat, kod. Przepisz
  je bez zmian, każdy osobno; co najmniej trzy znaki.
- `words` — słowa kluczowe; odmiana nie ma znaczenia.

Podaj co najmniej jedno pole.
