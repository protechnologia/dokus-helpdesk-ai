<!-- Opis narzędzia `read_docs` w grafie `search` — czyta go MODEL razem ze schematem
     argumentów (`ReadDocsQuery` bez docstringów). Szkielet; narzędzie właściwe w p. 52,
     treść opisu stroi się z promptem grafu w p. 23.

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
Odczytuje treść sekcji dokumentacji po identyfikatorach ze spisu treści albo z wyszukiwania.
Tylko odczytane sekcje trafiają na listę źródeł odpowiedzi: zanim oprzesz się na instrukcji,
przeczytaj ją.

- `section_ids` — od jednego do pięciu identyfikatorów, dokładnie w brzmieniu z nawiasu
  kwadratowego. Nieznany identyfikator kończy się błędem, bez wyniku częściowego.

Każda sekcja niesie wersję i datę wydania dokumentu — instrukcja do starszej wersji może już nie
obowiązywać.
