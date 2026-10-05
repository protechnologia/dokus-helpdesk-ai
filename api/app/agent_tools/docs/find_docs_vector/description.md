<!-- Opis narzędzia `find_docs_vector` — czyta go MODEL razem ze
     schematem argumentów (`FindDocsVectorQuery` bez docstringów),
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

Szuka w bazie wektorowej sekcji instrukcji i dokumentacji aplikacji
o podanej tematyce: po znaczeniu, nie słowo w słowo. Zapytanie jest
zamieniane na embedding i porównywane z fragmentami sekcji.

# Jak wywoływać

| argument | typ   | co podać               | przykład                               | opis |
|----------|-------|------------------------|----------------------------------------|------|
| text     | tekst | temat własnymi słowami | "kto nadaje uprawnienie do kancelarii" | Temat szukanej sekcji, zdaniem albo kilkoma słowami. Znajduje sekcję także wtedy, gdy używa ona innych sformułowań. |

# Co zwraca

JSON z opisami sekcji, bez treści:

| pole                    | co zawiera                           |
|-------------------------|--------------------------------------|
| sections                | sekcje, od najbardziej podobnej      |
| sections[].score        | podobieństwo cosinusowe do zapytania |
| sections[].section      | opis sekcji                          |
| dropped_below_threshold | ile sekcji odpadło jako zbyt słabe   |

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

- Dosłowną nazwę opcji, komunikat albo kod pewniej znajdzie
  `find_docs_text`.
- Treść wybranych sekcji odczytasz narzędziem `read_docs`.
- Wynik ma limit długości i próg podobieństwa: sekcje pasujące zbyt
  słabo odpadają i są tylko policzone w `dropped_below_threshold`.
  Pusty wynik znaczy, że żadna sekcja nie pasuje wystarczająco:
  spróbuj innego sformułowania albo przyjmij, że dokumentacja tego
  nie opisuje.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
