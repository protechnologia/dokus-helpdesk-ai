<!-- Opis narzędzia `read_code_file` — czyta go MODEL razem ze
     schematem argumentów (`ReadCodeFileQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Liczba 300 w zasadach to `MAX_LINES_PER_READ` z `models.py`;
     pilnuje jej test opisu.

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Pozwala ci przeczytać kod źródłowy aplikacji: plik w całości albo
wskazane linie, każdą z numerem. Użyj, gdy szukanie
(`find_code_text`) wskazało linię, a ty chcesz wiedzieć, w jakiej
funkcji ona leży i przy jakim warunku kod do niej dochodzi.

# Jak wywoływać

| argument  | typ    | co podać               | przykład                                      | opis |
|-----------|--------|------------------------|-----------------------------------------------|------|
| path      | tekst  | ścieżka pliku          | "src/lib/Urzad/Numeracja/GeneratorNumeru.php" | Ścieżka pliku w kodzie aplikacji, względem jego katalogu głównego, w brzmieniu z wyniku szukania. Ścieżka spoza kodu, katalog albo plik, którego nie ma, kończy się błędem. |
| from_line | liczba | pierwsza linia zakresu | 10                                            | Opcjonalna. Numer linii w pliku, liczony od 1; bez niej odczyt zaczyna się od pierwszej linii. Linia za końcem pliku kończy się błędem. |
| to_line   | liczba | ostatnia linia zakresu | 60                                            | Opcjonalna. Nie mniejsza niż `from_line`; bez niej odczyt idzie do końca pliku. Linia za końcem pliku nie jest błędem: dostajesz linie do końca pliku. |

Bez `from_line` i `to_line` prosisz o cały plik.

# Co zwraca

JSON z liniami pliku i z tym, który zakres dostałeś:

| pole                  | co zawiera                               |
|-----------------------|------------------------------------------|
| path                  | ścieżka pliku w kodzie aplikacji         |
| file_info.total_lines | ile linii ma cały plik                   |
| requested.from_line   | pierwsza żądana linia                    |
| requested.to_line     | ostatnia żądana linia; `null`: do końca  |
| returned.from_line    | pierwsza oddana linia                    |
| returned.to_line      | ostatnia oddana linia                    |
| returned.cut_by_limit | `true`: limit urwał żądany zakres        |
| returned.end_of_file  | `true`: oddano plik do ostatniej linii   |
| lines[].line          | numer linii w pliku, liczony od 1        |
| lines[].text          | treść linii, z wcięciem                  |

# Zasady

- Po trafieniu z `find_code_text` czytaj otoczenie linii:
  kilkadziesiąt linii przed nią i po niej. Mały plik możesz
  przeczytać w całości.
- Jedno wywołanie oddaje najwyżej 300 linii. Gdy
  `returned.cut_by_limit` jest `true`, limit urwał odczyt: dalsze
  linie przeczytaj od `returned.to_line` + 1.
- Gdy `returned.end_of_file` jest `true`, plik się skończył i dalej
  nic nie ma. Gdy obie flagi są `false`, dostałeś dokładnie żądany
  zakres, a plik ma dalsze linie.
- Ścieżkę z `path` i numery z `lines[].line` podajesz narzędziu
  `quote_code`, gdy cytujesz przeczytany fragment.
- Sam odczyt nie trafia na listę źródeł odpowiedzi. Źródłem jest
  dopiero fragment zacytowany narzędziem `quote_code` jako
  przyczyna.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
