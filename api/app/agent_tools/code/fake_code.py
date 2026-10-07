"""
Description:
Zmyślone pliki kodu, na których stoją atrapy narzędzi kodu. Jedno miejsce, żeby ścieżka
i numery linii z jednej atrapy pasowały do drugiej — tak jak na produkcji, gdzie wszystkie
narzędzia kodu czytają tę samą paczkę.

| plik                                          | linii | po co jest w zestawie                    |
|-----------------------------------------------|-------|------------------------------------------|
| `src/lib/Urzad/Numeracja/GeneratorNumeru.php` | 14    | przyczyna: warunek i treść komunikatu    |
| `src/web/js/_global/bledy.js`                 | 8     | miejsce do wykluczenia: ogólny komunikat |

O czym pamiętać przy zmianach:

- Kod jest wymyślony, nigdy kopiowany z kodu klienta. Leży w tym samym zmyślonym świecie co
  zgłoszenia atrap: zgłoszenie 90012 to brak sekwencji numeracji.
- Ścieżki i numery linii są stałe: testy odwołują się do nich wprost.
- Linie dzieli `\\n`, jak w paczce; atrapy liczą je tą samą funkcją co czytnik paczki.
"""

GENERATOR_PATH = "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
ERRORS_PATH    = "src/web/js/_global/bledy.js"

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
