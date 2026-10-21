<!-- Opis narzędzia `read_code_symbol` — czyta go MODEL razem ze
     schematem argumentów (`ReadCodeSymbolQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Liczby 300 i 20 w zasadach to `MAX_LINES_PER_SYMBOL`
     i `MAX_CANDIDATES` z `models.py`; pilnuje ich test opisu.

     Zasady nazywają całą drogę po wyniku: zawężenie `path`, odczyt
     pliku (`read_code_file`), szukanie (`find_code_text`)
     i cytowanie (`quote_code`).

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Pozwala ci przeczytać jedną funkcję, metodę albo klasę z kodu
aplikacji w całości, po nazwie, bez zgadywania zakresu linii. Użyj,
gdy znasz nazwę: z pola `symbol` w wyniku szukania
(`find_code_text`) albo z wywołania w przeczytanym kodzie.

# Jak wywoływać

| argument | typ    | przykłady                 | opis |
|----------|--------|---------------------------|------|
| name     | string | "nastepnyNumer"           | Nazwa funkcji, metody albo klasy, z zachowaniem wielkości liter. Możesz podać ją razem z klasą albo obiektem, w którym leży: `GeneratorNumeru::nastepnyNumer`, `APP.pisma.wyslijHandler`. Przestrzeń nazw przed nazwą klasy jest pomijana. |
| path     | string | "src/lib/Urzad/Numeracja" | Opcjonalne zawężenie: szuka definicji tylko w tym pliku albo w tym katalogu z podkatalogami. Bez niego szuka w całym kodzie. Ścieżka względem katalogu głównego kodu; ścieżka spoza kodu albo taka, której nie ma, kończy się błędem. |

# Co zwraca

JSON z jedną definicją i jej liniami albo z listą kandydatów:

| pole                   | co zawiera                               |
|------------------------|------------------------------------------|
| requested.name         | nazwa, o którą prosiłeś                  |
| requested.path         | zawężenie; `null`: cały kod              |
| symbol                 | jedyna pasująca definicja; `null`: kilka |
| symbol.path            | plik, w którym leży definicja            |
| symbol.name            | nazwa definicji                          |
| symbol.scope           | klasa albo obiekt, w którym leży         |
| symbol.kind            | `function`, `method`, `class`…           |
| symbol.from_line       | pierwsza linia definicji                 |
| symbol.to_line         | ostatnia linia definicji                 |
| returned.from_line     | pierwsza oddana linia                    |
| returned.to_line       | ostatnia oddana linia                    |
| returned.cut_by_limit  | `true`: limit urwał definicję            |
| numbered_lines         | linie z numerami; `null`: kilka          |
| candidates             | pasujące definicje, gdy jest ich kilka   |
| candidates[].path      | plik kandydata                           |
| candidates[].name      | nazwa kandydata                          |
| candidates[].scope     | klasa albo obiekt, w którym leży         |
| candidates[].kind      | `function`, `method`, `class`…           |
| candidates[].from_line | pierwsza linia kandydata                 |
| candidates[].to_line   | ostatnia linia kandydata                 |
| omitted_over_limit     | ilu kandydatów jest ponad limit listy    |

# Zasady

- Treść dostajesz tylko wtedy, gdy do nazwy pasuje dokładnie jedna
  definicja. Gdy pasuje kilka, `symbol` jest `null`, a `candidates`
  wymienia je bez treści: powtórz wywołanie z `path` zawężonym do
  pliku właściwego kandydata.
- Kandydatów z tego samego pliku nie rozdzieli żadne `path`:
  wybranego przeczytaj narzędziem `read_code_file`, podając jego
  `from_line` i `to_line`.
- Ta sama nazwa bywa zdefiniowana w wielu plikach, na przykład
  akcja o tej samej nazwie w kilku modułach. Gdy znasz plik albo
  katalog, podaj go w `path`.
- Metody, której nie ma w pliku klasy, szukaj w jej katalogu:
  bywa zdefiniowana w klasie bazowej, która leży obok. Podaj samą
  nazwę metody, a w `path` katalog zamiast pliku.
- Lista kandydatów ma najwyżej 20 pozycji; pozostałe są policzone
  w `omitted_over_limit`. Wartość większa od zera znaczy, że trzeba
  zawęzić `path`.
- Jedno wywołanie oddaje najwyżej 300 linii. Gdy
  `returned.cut_by_limit` jest `true`, dalsze linie przeczytaj
  narzędziem `read_code_file`: od `returned.to_line` + 1 do
  `symbol.to_line`.
- Funkcja podana jako argument wewnątrz innej funkcji nie ma własnej
  definicji: przeczytaj funkcję, w której leży.
- Brak definicji kończy się błędem, który mówi, czy nazwa jest
  w kodzie gdzie indziej. Gdy nie ma jej wcale, może pochodzić
  z biblioteki albo powstawać w trakcie działania: poszukaj jej
  narzędziem `find_code_text`.
- Każda linia w `numbered_lines` to numer linii w pliku (od 1),
  tabulator i treść linii z wcięciem. Numer nie należy do kodu.
- Ścieżkę z `symbol.path` i numery linii z `numbered_lines`
  podajesz narzędziu `quote_code`, gdy cytujesz przeczytany
  fragment.
- Sam odczyt nie trafia na listę źródeł odpowiedzi. Źródłem jest
  dopiero fragment zacytowany narzędziem `quote_code` jako
  przyczyna.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
