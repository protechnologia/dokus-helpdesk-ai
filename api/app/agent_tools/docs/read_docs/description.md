<!-- Opis narzędzia `read_docs` — czyta go MODEL razem ze schematem argumentów
     (`ReadDocsQuery` bez docstringów), w każdym grafie, który ma to narzędzie
     na liście. Mówi, jak pytać narzędzie i co ono oddaje; po co wyniki w danej
     funkcji, mówi prompt grafu. Szkielet; narzędzie właściwe w p. 52.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego trzeba
     przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Odczytuje treść sekcji dokumentacji po identyfikatorach ze spisu treści albo z
wyszukiwania. Tylko odczytane sekcje trafiają na listę źródeł odpowiedzi: zanim
oprzesz się na instrukcji, przeczytaj ją.

- `section_ids` — od jednego do pięciu identyfikatorów, dokładnie w brzmieniu z
  pola `section_id`. Nieznany identyfikator kończy się błędem, bez wyniku
  częściowego.

Każda sekcja niesie wersję i datę wydania dokumentu — instrukcja do starszej
wersji może już nie obowiązywać.

Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu narzędzie
zwraca błąd zamiast wyniku.
