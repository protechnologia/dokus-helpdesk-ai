<!-- Opis narzędzia `list_docs` — czyta go MODEL razem ze schematem
     argumentów (`ListDocsArgs` bez docstringów), w każdym grafie,
     który ma to narzędzie na liście. Mówi, jak pytać narzędzie i co
     ono oddaje; po co wyniki w danej funkcji, mówi prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
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

JSON z opisami sekcji, bez treści:

| pole                    | co zawiera                           |
|-------------------------|--------------------------------------|
| sections                | opisy wszystkich sekcji dokumentacji |
| sections[].section_id   | identyfikator dla `read_docs`        |
| sections[].document     | tytuł dokumentu                      |
| sections[].version      | wydanie dokumentu                    |
| sections[].date         | data wydania                         |
| sections[].chapter_path | rozdział, w którym sekcja leży       |
| sections[].title        | tytuł sekcji                         |
| sections[].description  | krótki opis, o czym jest sekcja      |

# Zasady

- Treść wybranych sekcji odczytasz narzędziem `read_docs`, podając
  ich identyfikatory.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
