<!-- Opis narzędzia `list_docs` — czyta go MODEL razem ze schematem
     argumentów (`ListDocsArgs` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co
     ono oddaje; po co wyniki w danej funkcji, mówi prompt grafu.
     Szkielet; narzędzie właściwe w p. 51.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty i pola wyniku w tabelkach, linie do 70 znaków —
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Zwraca spis treści dokumentacji aplikacji. Spis mówi, gdzie co jest,
a nie co tam stoi.

# Jak wywoływać

Bez argumentów.

# Co zwraca

JSON:

| pole     | co zawiera                           |
|----------|--------------------------------------|
| sections | opisy wszystkich sekcji dokumentacji |

Pola opisu sekcji:

| pole         | co zawiera                                     |
|--------------|------------------------------------------------|
| section_id   | identyfikator sekcji — podajesz go `read_docs` |
| document     | tytuł dokumentu                                |
| version      | wydanie dokumentu                              |
| date         | data wydania                                   |
| chapter_path | rozdział, w którym sekcja leży                 |
| title        | tytuł sekcji                                   |
| description  | krótki opis, o czym jest sekcja                |

# Zasady

- Treść wybranych sekcji odczytasz narzędziem `read_docs`, podając
  ich identyfikatory.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
