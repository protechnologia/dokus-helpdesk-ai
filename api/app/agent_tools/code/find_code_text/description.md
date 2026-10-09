<!-- Opis narzędzia `find_code_text` — czyta go MODEL razem ze
     schematem argumentów (`FindCodeTextQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Liczby 20 i 200 w zasadach to `MAX_LINES_PER_SEARCH`
     i `MAX_TEXT_CHARS` z `models.py`, a „trzy znaki" przy `words` to
     `MIN_LONGEST_WORD_CHARS`; pilnuje ich test opisu.

     Zasady nie wymieniają jeszcze narzędzi odczytu kodu po nazwie:
     dojdą razem z nimi (p. 63, 66). Do tego czasu model nie ma czym
     przeczytać otoczenia znalezionej linii.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Szuka w kodzie źródłowym aplikacji linii, w których stoi podany
tekst: po dosłownym brzmieniu i po słowach, nie po znaczeniu. Użyj,
gdy zgłoszenie niesie komunikat z ekranu, wpis z logu albo kod
błędu: wynik mówi, w których plikach i liniach kodu ten tekst stoi.

# Jak wywoływać

| argument | typ   | co podać                    | przykład                   | opis |
|----------|-------|-----------------------------|----------------------------|------|
| exact    | tekst | fraza wyszukiwana dosłownie | "Brak sekwencji numeracji" | W podanej kolejności, bez względu na wielkość liter. Cała fraza musi stać w jednej linii kodu. Przepisz ją bez zmian; co najmniej trzy znaki. |
| words    | tekst | słowa oddzielone spacją     | "sekwencji numeracji"      | Linia kodu musi zawierać wszystkie, w dowolnej kolejności, bez względu na wielkość liter. Bez odmiany: słowo jest szukane jako ciąg znaków („limit" znajdzie „limitu", ale nie odwrotnie). Co najmniej jedno słowo ma mieć trzy znaki. |
| path     | tekst | katalog albo plik           | "src/web/js"               | Opcjonalne zawężenie: szuka tylko w tym katalogu z podkatalogami albo w tym pliku. Ścieżka względem katalogu głównego kodu; ścieżka spoza kodu albo taka, której nie ma, kończy się błędem. |

Podaj `exact`, `words` albo oba. Każde szuka osobno, a wyniki się
sumują: linia wraca, gdy zawiera frazę z `exact` albo wszystkie
słowa z `words`.

# Co zwraca

JSON z liniami kodu:

| pole               | co zawiera                                   |
|--------------------|----------------------------------------------|
| lines              | trafienia frazą pierwsze, po ścieżce i linii |
| lines[].path       | ścieżka pliku w kodzie aplikacji             |
| lines[].line       | numer linii w pliku, liczony od 1            |
| lines[].matched_by | czym znaleziona: `exact` albo `words`        |
| lines[].text       | treść tej jednej linii, bez wcięcia          |
| omitted_over_limit | ile pasujących linii ponad limit wyniku      |

# Zasady

- Komunikat z ekranu bywa w kodzie składany z części. Szukaj jego
  stałego fragmentu, bez numerów, nazw plików i nazw własnych.
- Ten sam komunikat miewa w kodzie kilka brzmień, także o innym
  szyku słów: gdy fraza daje mało, powtórz ją słowami.
- Jedno wywołanie to jedna fraza: kolejną frazę sprawdź osobnym
  wywołaniem.
- Wynik ma najwyżej 20 linii; pasujące ponad limit są tylko
  policzone w `omitted_over_limit`. Wartość większa od zera znaczy,
  że trzeba zawęzić: dłuższą frazą albo katalogiem w `path`.
- `text` to jedna linia, ucięta po 200 znakach (kończy się wtedy
  znakiem „…"). Pokazuje, gdzie tekst stoi, a nie w jakim warunku
  kod do niego dochodzi.
- Jako przyczynę (narzędzie `quote_code`) wskazuj fragment dopiero
  wtedy, gdy przeczytałeś jego otoczenie, a nie samą trafioną linię.
- Pusta lista znaczy, że takiego tekstu nie ma w kodzie aplikacji:
  może pochodzić z biblioteki zewnętrznej, z bazy danych albo
  z innego systemu.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
