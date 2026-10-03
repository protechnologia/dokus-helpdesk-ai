<!-- Opis narzędzia `find_tickets_text` w grafie `suggest_questions` — czyta go MODEL razem ze schematem
     argumentów (`FindTicketsTextQuery` bez docstringów). Szkielet; narzędzie właściwe w p. 53,
     treść opisu stroi się z promptem grafu w p. 25.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń po dosłownym brzmieniu, nie po znaczeniu. Zwraca te same
rekordy co `find_tickets_vector`, z informacją, czym każdy został znaleziony.

Użyj, gdy zgłoszenie niesie coś, co da się znaleźć słowo w słowo:

- `exact` — dosłowne ciągi: kod błędu, sygnatura, fragment komunikatu z ekranu. Przepisz je bez
  zmian, każdy osobno; co najmniej trzy znaki.
- `words` — słowa kluczowe; odmiana nie ma znaczenia („załącznik" znajdzie „załączników").

Podaj co najmniej jedno pole. Ten sam komunikat miewa różne przyczyny: trafienie mówi, że taki
objaw już był, a nie co go wywołało.
