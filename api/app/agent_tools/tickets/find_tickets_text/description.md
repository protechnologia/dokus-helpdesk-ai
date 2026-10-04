<!-- Opis narzędzia `find_tickets_text` — czyta go MODEL razem ze schematem
     argumentów (`FindTicketsTextQuery` bez docstringów), w każdym grafie, który
     ma to narzędzie na liście. Mówi, jak pytać narzędzie i co ono oddaje; po co
     wyniki w danej funkcji, mówi prompt grafu. Szkielet; narzędzie właściwe w
     p. 53.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Szuka w bazie historycznych zgłoszeń po dosłownym brzmieniu, nie po znaczeniu —
w oryginalnych wątkach, nie w kartach. Zwraca oryginalne wątki: temat, opis
zgłaszającego i komentarze, z informacją, czym zgłoszenie zostało znalezione.
Kart tu nie ma: przyczynę i rozwiązanie wyczytaj z komentarzy.

Użyj, gdy zgłoszenie niesie coś, co da się znaleźć słowo w słowo:

- `exact` — dosłowne ciągi: kod błędu, sygnatura, fragment komunikatu z ekranu.
  Przepisz je bez zmian, każdy osobno; co najmniej trzy znaki.
- `words` — słowa kluczowe; odmiana nie ma znaczenia („załącznik" znajdzie
  „załączników").

Podaj co najmniej jedno pole. Ten sam komunikat miewa różne przyczyny: trafienie
mówi, że taki objaw już był, a nie co go wywołało.
