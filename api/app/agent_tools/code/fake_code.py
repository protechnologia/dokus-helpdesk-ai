"""
Description:
Zmyślone pliki kodu, na których stoją atrapy narzędzi kodu. Jedno miejsce, żeby ścieżka
i numery linii z jednej atrapy pasowały do drugiej — tak jak na produkcji, gdzie wszystkie
narzędzia kodu czytają tę samą paczkę.

| plik                                          | linii | po co jest w zestawie                    |
|-----------------------------------------------|-------|------------------------------------------|
| `src/lib/Urzad/Numeracja/GeneratorNumeru.php` | 14    | przyczyna: warunek i treść komunikatu    |
| `src/web/js/_global/bledy.js`                 | 8     | miejsce do wykluczenia: ogólny komunikat |

Obok plików stoi to, co paczka trzyma poza kodem: zmyślony opis projektu (`PROJECT_DESCRIPTION`)
i metryczka (`default_package_info()`), na których stoi atrapa `describe_code`, oraz mapa
symboli (`default_symbol_map()`), z której atrapy `read_code_symbol` i `find_code_text` biorą
granice funkcji.

O czym pamiętać przy zmianach:

- Kod jest wymyślony, nigdy kopiowany z kodu klienta. Leży w tym samym zmyślonym świecie co
  zgłoszenia atrap: zgłoszenie 90012 to brak sekwencji numeracji.
- Ścieżki i numery linii są stałe: testy odwołują się do nich wprost.
- Linie dzieli `\\n`, jak w paczce; atrapy liczą je tą samą funkcją co czytnik paczki.
- Opis projektu wymienia katalogi obu plików, więc katalog wzięty z opisu atrapa spisu pokaże.
  Katalog dopisany do opisu musi mieć tu plik.
- Mapa symboli jest spisana ręcznie, bo `api` kodu nie rozbiera. Test porównuje ją z mapą,
  którą dla tych samych plików buduje skrypt paczki, więc po zmianie pliku trzeba ją poprawić.
"""

from datetime import date

from app.core_model.code.code_package_info import CodePackageInfo
from app.core_model.code.code_symbol import CodeSymbol
from app.core_model.code.code_symbol_map import CodeSymbolMap

GENERATOR_PATH = "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
ERRORS_PATH    = "src/web/js/_global/bledy.js"

# Katalogi, które wymienia zmyślony opis projektu: w każdym leży jeden z plików wyżej.
BACKEND_DIR   = "src/lib/Urzad"
INTERFACE_DIR = "src/web/js"

PROJECT_DESCRIPTION = (
    f"Zmyślona aplikacja urzędu na Symfony 1: backend w PHP (kod domenowy w `{BACKEND_DIR}/`), "
    f"interfejs w JS (`{INTERFACE_DIR}/`, katalog na moduł, część wspólna "
    f"w `{INTERFACE_DIR}/_global/`)."
)

# Dzień budowy zmyślonej paczki; gałęzi nie ma, jak w paczce z aplikacji syntetycznej.
PACKAGE_BUILT_ON = date(2026, 10, 1)

GENERATOR_CODE = "\n".join([
    "<?php",
    "",
    "class GeneratorNumeru",
    "{",
    "    public function nastepnyNumer($rok)",
    "    {",
    "        $sekwencja = SekwencjaNumeracjiTable::getInstance()->find($rok);",
    "        if (!$sekwencja) {",
    "            throw new BrakSekwencjiException('Brak sekwencji numeracji dla roku ' . $rok);",
    "        }",
    "",
    "        return $sekwencja->nastepny . '/' . $rok;",
    "    }",
    "}",
])
ERRORS_CODE = "\n".join([
    "$(document).ajaxError(function (zdarzenie, odpowiedz) {",
    "    if (odpowiedz.status === 401) {",
    "        pokazBlad('Sesja wygasła. Zaloguj się ponownie.');",
    "        return;",
    "    }",
    "",
    "    pokazBlad('Nie udało się skomunikować z serwerem');",
    "});",
])


def default_files() -> dict[str, str]:
    """
    Description:
    Dwa zmyślone pliki: ścieżka w paczce → treść.

    Example args:
        (brak)

    Example result:
        {"src/lib/Urzad/Numeracja/GeneratorNumeru.php": "<?php\\n\\nclass GeneratorNumeru…",
         "src/web/js/_global/bledy.js": "$(document).ajaxError(function (zdarzenie, …"}
    """
    files = {
        GENERATOR_PATH: GENERATOR_CODE,
        ERRORS_PATH:    ERRORS_CODE,
    }

    return files


def default_package_info() -> CodePackageInfo:
    """
    Description:
    Metryczka zmyślonej paczki: bez gałęzi, ze stałym dniem budowy.

    Example args:
        (brak)

    Example result:
        CodePackageInfo(branch=None, built_on=date(2026, 10, 1))
    """
    return CodePackageInfo(branch=None, built_on=PACKAGE_BUILT_ON)


def default_symbol_map() -> CodeSymbolMap:
    """
    Description:
    Mapa symboli zmyślonych plików: klasa generatora i jej jedyna metoda. Plik obsługi błędów
    ma samą funkcję bez nazwy, podaną jako argument, więc symboli nie ma i w mapie go nie ma.

    Example args:
        (brak)

    Example result:
        CodeSymbolMap(built_on=date(2026, 10, 1), syntax_errors=[],
                      files={"src/lib/Urzad/Numeracja/GeneratorNumeru.php": [
                          CodeSymbol(name="GeneratorNumeru", kind="class", from_line=3, …),
                          CodeSymbol(name="nastepnyNumer", kind="method", from_line=5, …)]})
    """
    symbol_map = CodeSymbolMap(
        built_on      = PACKAGE_BUILT_ON,
        syntax_errors = [],
        files         = {
            GENERATOR_PATH: [
                CodeSymbol(
                    name      = "GeneratorNumeru",
                    scope     = None,
                    kind      = "class",
                    from_line = 3,
                    to_line   = 14,
                ),
                CodeSymbol(
                    name      = "nastepnyNumer",
                    scope     = "GeneratorNumeru",
                    kind      = "method",
                    from_line = 5,
                    to_line   = 13,
                ),
            ],
        },
    )

    return symbol_map
