<!-- Opis narzędzia `find_docs_text` w grafie `suggest_questions` — czyta go MODEL razem ze schematem
     argumentów (`FindDocsTextQuery` bez docstringów). Szkielet; narzędzie właściwe w p. 50,
     treść opisu stroi się z promptem grafu w p. 25.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka sekcji dokumentacji aplikacji po dosłownym brzmieniu, nie po znaczeniu. Zwraca wiersze
spisu treści z dopasowanym fragmentem zdania — bez treści sekcji. Treść wybranych sekcji
odczytasz narzędziem `read_docs`.

- `exact` — dosłowne ciągi: nazwa opcji lub przycisku, komunikat, kod. Przepisz je bez zmian,
  każdy osobno; co najmniej trzy znaki.
- `words` — słowa kluczowe; odmiana nie ma znaczenia.

Podaj co najmniej jedno pole.
