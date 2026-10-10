<!-- Opis narzędzia `list_code_files` — czyta go MODEL razem ze
     schematem argumentów (`ListCodeFilesQuery` bez docstringów),
     w każdym grafie, który ma to narzędzie na liście. Mówi, jak pytać
     narzędzie i co ono oddaje; po co wyniki w danej funkcji, mówi
     prompt grafu.

     Układ jest ten sam w każdym opisie narzędzia: cztery sekcje,
     argumenty w tabelce, wynik w JEDNEJ tabelce — pola zagnieżdżone
     pełną ścieżką (`sections[].section.title`), linie do 70 znaków;
     dłuższe bywają tylko wiersze tabelki argumentów.

     Liczba 200 w zasadach to `MAX_ENTRIES_PER_LISTING`, a 2 w tabelce
     argumentów to `DEFAULT_DEPTH` z `models.py`; obu pilnuje test
     opisu. Zasady wymieniają po nazwie odczyt pliku (`read_code_file`)
     i szukanie (`find_code_text`).

     Zmiana dotyczy wszystkich grafów naraz, więc po strojeniu jednego
     trzeba przemierzyć pozostałe (p. 23, 25–26).

     Komentarze redakcyjne jak ten są wycinane przed wysłaniem. -->
# Do czego służy

Pokazuje ci, jakie katalogi i pliki ma kod źródłowy aplikacji pod
wskazanym katalogiem. Użyj, gdy szukanie (`find_code_text`) daje za
dużo trafień i chcesz je zawęzić do katalogu, albo gdy chcesz
zobaczyć, co leży obok znalezionego pliku.

# Jak wywoływać

| argument | typ    | co podać             | przykład                | opis |
|----------|--------|----------------------|-------------------------|------|
| path     | tekst  | ścieżka katalogu     | "src/lib/Urzad/Wysylka" | Opcjonalna. Ścieżka katalogu w kodzie aplikacji, względem jego katalogu głównego; bez niej dostajesz spis katalogu głównego. Ścieżka spoza kodu, plik albo katalog, którego nie ma, kończy się błędem. |
| depth    | liczba | ile poziomów pokazać | 2                       | Opcjonalna, domyślnie 2. Przy 1 dostajesz sam katalog, przy 2 także zawartość jego podkatalogów, i tak dalej. |

Bez argumentów prosisz o dwa poziomy od katalogu głównego kodu.

# Co zwraca

JSON ze spisem katalogu i z tym, jaką głębokość dostałeś:

| pole                        | co zawiera                                 |
|-----------------------------|--------------------------------------------|
| path                        | ścieżka katalogu; `.` to katalog główny    |
| dir_info.total_depth        | ile poziomów ma wszystko pod katalogiem    |
| requested.depth             | żądana głębokość                           |
| returned.depth              | oddana głębokość                           |
| returned.depth_cut_by_limit | `true`: limit zmniejszył głębokość         |
| returned.has_more_depth     | `true`: głębiej są pozycje spoza wyniku    |
| returned.omitted_over_limit | ile pozycji katalogu nie weszło do wyniku  |
| entries[].path              | pełna ścieżka pozycji w kodzie aplikacji   |
| entries[].kind              | `dir`: katalog, `file`: plik               |

# Zasady

- Pozycje stoją w kolejności drzewa: katalog, a pod nim jego
  zawartość. W jednym katalogu podkatalogi stoją przed plikami.
- Wynik ma najwyżej 200 pozycji. Gdy żądana głębokość się w nich nie
  mieści, dostajesz mniej poziomów, a `returned.depth_cut_by_limit`
  jest `true`. Poziomy, które widzisz, są pełne: głębiej zajrzyj
  spisem wybranego podkatalogu.
- Gdy `returned.omitted_over_limit` jest większe od zera, sam
  katalog ma więcej pozycji, niż mieści wynik: widzisz jego
  podkatalogi i początek plików. Reszty spisem nie zobaczysz. Szukaj
  w tym katalogu narzędziem `find_code_text`, podając go w `path`.
- Gdy `returned.has_more_depth` jest `true`, katalogi z ostatniego
  pokazanego poziomu mają zawartość, której tu nie widać.
  `dir_info.total_depth` mówi, o jaką głębokość poprosić, żeby
  zobaczyć wszystko.
- Ścieżki z `entries[].path` podajesz dalej bez zmian: plik
  narzędziu `read_code_file`, a katalog szukaniu (`find_code_text`,
  w `path`) albo kolejnemu spisowi.
- Nazwa pliku nie mówi, co w nim stoi. Zanim coś na niej oprzesz,
  przeczytaj plik narzędziem `read_code_file`.
- Sam spis nie trafia na listę źródeł odpowiedzi.
- Limit wywołań w jednej sprawie: {{max_calls}}. Po jego wyczerpaniu
  narzędzie zwraca błąd zamiast wyniku.
