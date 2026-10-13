"""
Description:
Narzędzia agenta na kodzie źródłowym aplikacji. Kod czyta się inaczej niż zgłoszenia
i dokumentację: model chodzi po plikach, a przechodzi przez wiele więcej, niż potrzebuje do
odpowiedzi. Dlatego odczyt kodu źródeł nie tworzy — robi to osobne narzędzie cytujące, którym
model wskazuje fragment powodujący opisane zachowanie.

| co                  | co zawiera                                                             |
|---------------------|------------------------------------------------------------------------|
| `fake_code.py`      | zmyślone pliki, opis projektu i mapa symboli, na których stoją atrapy  |
| `describe_code/`    | opis projektu w całości, z gałęzią paczki; źródeł nie tworzy           |
| `find_code_text/`   | szukanie linii z podanym tekstem: ścieżka, numer, funkcja i treść      |
| `list_code_files/`  | spis katalogu do wskazanej głębokości; źródeł nie tworzy               |
| `read_code_file/`   | odczyt pliku albo zakresu linii, z numerami; źródeł nie tworzy         |
| `read_code_symbol/` | odczyt jednej funkcji, metody albo klasy po nazwie; źródeł nie tworzy  |
| `quote_code/`       | cytowanie fragmentu pliku: przyczyna trafia na listę źródeł odpowiedzi |

Narzędzia właściwe stoją na paczce kodu na dysku (`CodePackage` z
`core_service/loader_code_package.py`), bez bazy; szuka w niej program ripgrep, uruchamiany
przez `engine_process/`. Opis projektu to plik `project.md` w paczce, obok kodu: pisze go
człowiek. Granice funkcji pochodzą z mapy symboli paczki (`symbols.json`), którą buduje skrypt
`scripts/build_code_symbols.py`: z niej `read_code_symbol` bierze zakres linii funkcji,
a `find_code_text` nazwę funkcji, w której leży znaleziona linia.

Narzędzie importuje się z jego pakietu
(`from app.agent_tools.code.quote_code import QuoteCodeTool`), nie stąd.
"""
