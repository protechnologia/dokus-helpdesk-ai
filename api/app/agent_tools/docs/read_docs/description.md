<!-- Opis narzędzia `read_docs` — czyta go MODEL razem ze schematem
     argumentów (`ReadDocsQuery` bez docstringów), w każdym grafie,
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

Odczytuje treść sekcji dokumentacji po identyfikatorach ze spisu
treści albo z wyszukiwania.

# Jak wywoływać

| argument    | typ           | co podać              | przykład                                  | opis |
|-------------|---------------|-----------------------|-------------------------------------------|------|
| section_ids | lista tekstów | identyfikatory sekcji | ["usr-odswiezanie", "adm-role-i-profile"] | Od jednego do pięciu identyfikatorów, dokładnie w brzmieniu z pola `section_id`. Nieznany identyfikator kończy się błędem, bez wyniku częściowego. |

# Co zwraca

JSON:

| pole                            | co zawiera                      |
|---------------------------------|---------------------------------|
| sections                        | odczytane sekcje                |
| sections[].section              | opis sekcji                     |
| sections[].section.section_id   | identyfikator sekcji            |
| sections[].section.document     | tytuł dokumentu                 |
| sections[].section.version      | wydanie dokumentu               |
| sections[].section.date         | data wydania                    |
| sections[].section.chapter_path | rozdział, w którym sekcja leży  |
| sections[].section.title        | tytuł sekcji                    |
| sections[].section.description  | krótki opis, o czym jest sekcja |
| sections[].text                 | treść sekcji                    |

# Zasady

- Tylko odczytane sekcje trafiają na listę źródeł odpowiedzi: zanim
  oprzesz się na instrukcji, przeczytaj ją.
- Każda sekcja niesie wersję i datę wydania dokumentu — instrukcja do
  starszej wersji może już nie obowiązywać.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
