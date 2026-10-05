<!-- Opis narzędzia `find_docs_text` — czyta go MODEL razem ze
     schematem argumentów (`FindDocsTextQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty i pola wyniku w tabelkach, linie do 70 znaków —
     dłuższe bywają tylko wiersze tabelki argumentów.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Szuka sekcji dokumentacji aplikacji w bazie pełnotekstowej: po
dosłownym brzmieniu i po słowach kluczowych, nie po znaczeniu.

# Jak wywoływać

| argument | typ   | co podać                    | przykład          | opis |
|----------|-------|-----------------------------|-------------------|------|
| exact    | tekst | fraza wyszukiwana dosłownie | "Przekaż bufor"   | Bez odmiany, w podanej kolejności, bez względu na wielkość liter. Nadaje się do nazwy opcji lub przycisku, komunikatu, kodu. Przepisz ją bez zmian; co najmniej trzy znaki. |
| words    | tekst | słowa kluczowe              | "limit załącznik" | Wyszukiwane w dowolnej odmianie i kolejności; sekcja musi zawierać wszystkie. Nadaje się do zagadnienia nazwanego kilkoma słowami. |

Podaj co najmniej jedno pole. Każde szuka osobno, a wyniki się
sumują: sekcja wraca, gdy zawiera frazę z `exact` albo wszystkie
słowa z `words`.

# Co zwraca

JSON z opisami sekcji, bez treści:

| pole                  | co zawiera                               |
|-----------------------|------------------------------------------|
| sections              | sekcje, dosłowne trafienia pierwsze      |
| sections[].matched_by | czym znaleziona: `exact` albo `words`    |
| sections[].section    | opis sekcji                              |
| omitted_over_limit    | ile pasujących sekcji ponad limit wyniku |

Pola opisu sekcji (`section`):

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

- Jedno wywołanie to jedna fraza: kolejną frazę sprawdź osobnym
  wywołaniem.
- Zagadnienie opisane własnymi słowami, bez znanej nazwy ani kodu,
  pewniej znajdzie `find_docs_vector`.
- Treść wybranych sekcji odczytasz narzędziem `read_docs`.
- Wynik ma limit długości: sekcje pasujące ponad niego są tylko
  policzone w `omitted_over_limit`. Wartość większa od zera znaczy,
  że zapytanie było zbyt ogólne.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
