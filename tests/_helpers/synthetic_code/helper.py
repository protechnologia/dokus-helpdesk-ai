"""
Description:
Paczka syntetycznej aplikacji i zestaw zapytań do niej, dla testów narzędzi kodu bez modelu.
Paczka powstaje skryptem ze źródła w `data/safe/code/source/`, a zbudowana leży obok, poza
commitem — test jej nie buduje (CLAUDE.md -> „Świadomie pominięte").

| helper                     | co oddaje                                                   |
|----------------------------|-------------------------------------------------------------|
| `synthetic_code_package()` | czytnik zbudowanej paczki syntetycznej                      |
| `synthetic_code_description()` | czytnik jej opisu projektu i metryczki                  |
| `synthetic_code_symbols()` | czytnik jej mapy symboli                                    |
| `synthetic_code_texts()`   | treść każdego pliku zbudowanej paczki, po ścieżce           |
| `synthetic_code_tools()`   | sześć prawdziwych narzędzi kodu na tej paczce               |
| `synthetic_code_cases()`   | sekcję jednego narzędzia z `code-synthetic.json`            |
| `synthetic_absent_paths()` | pliki ze źródła, których paczka nie może zawierać           |
| `line_of()`                | numer linii, w której stoi fragment zapisany w zestawie     |

Przykład — przypadek z zestawu zamieniony na argumenty narzędzia:

    package = synthetic_code_package()
    case    = synthetic_code_cases("quote_code")[0]

    line_of(package, case["query"]["path"], case["query"]["from_at"])  # np. 17

O czym pamiętać przy zmianach:

- Brak zbudowanej paczki to błąd z poleceniem budowy, nie pominięcie testu: test narzędzia kodu
  bez paczki nie ma na czym stanąć, a pominięty wyglądałby na zielony.
- Paczkę przebudowuje się po każdej zmianie źródła albo reguł. Nieaktualna daje mylące wyniki:
  helper nie porównuje jej ze źródłem.
- Zestaw trzyma miejsce w kodzie jako stały fragment linii, bez numeru, więc dopisanie linii
  w źródle nie psuje przypadków. Numer wylicza `line_of()` na zbudowanej paczce.
- Test samego skryptu paczki buduje własną paczkę w katalogu tymczasowym, ze źródła i reguł
  wskazanych tu stałymi; zbudowanej paczki obok źródła nie czyta ani nie zmienia.
"""

import json
from typing import Any

from app.agent_tools import AgentTool
from app.agent_tools.code.describe_code import DescribeCodeTool
from app.agent_tools.code.find_code_text import FindCodeTextTool
from app.agent_tools.code.list_code_files import ListCodeFilesTool
from app.agent_tools.code.quote_code import QuoteCodeTool
from app.agent_tools.code.read_code_file import ReadCodeFileTool
from app.agent_tools.code.read_code_symbol import ReadCodeSymbolTool
from app.core_service.loader_code_description import CodeDescription
from app.core_service.loader_code_package import CodePackage
from app.core_service.loader_code_symbols import CodeSymbols
from app.engine_process.ripgrep import RipgrepClient
from tests._helpers.synthetic_code.constants import (
    BUILD_COMMAND,
    SEARCH_TIMEOUT_SECONDS,
    SYNTHETIC_CASES_FILE,
    SYNTHETIC_PACKAGE_DIR,
)


def synthetic_code_package() -> CodePackage:
    """
    Description:
    Czytnik paczki zbudowanej z aplikacji syntetycznej. Odmawia, gdy paczki nie zbudowano.

    Example args:
        (brak)

    Example result:
        CodePackage czytająca z data/safe/code/repo

    Raises:
        AssertionError: paczki syntetycznej nie zbudowano
    """
    built = (SYNTHETIC_PACKAGE_DIR / "repo").is_dir()

    assert built, f"brak zbudowanej paczki syntetycznej — zbuduj ją: {BUILD_COMMAND}"

    return CodePackage(SYNTHETIC_PACKAGE_DIR)


def synthetic_code_description() -> CodeDescription:
    """
    Description:
    Czytnik opisu projektu i metryczki paczki syntetycznej. Opis (`project.md`) leży w repo
    obok źródła aplikacji, metryczkę zapisuje skrypt przy budowie — więc tak jak czytnik kodu
    odmawia, gdy paczki nie zbudowano.

    Example args:
        (brak)

    Example result:
        CodeDescription czytająca data/safe/code/project.md i manifest.json

    Raises:
        AssertionError: paczki syntetycznej nie zbudowano
    """
    built = (SYNTHETIC_PACKAGE_DIR / "manifest.json").is_file()

    assert built, f"brak zbudowanej paczki syntetycznej — zbuduj ją: {BUILD_COMMAND}"

    return CodeDescription(SYNTHETIC_PACKAGE_DIR)


def synthetic_code_symbols() -> CodeSymbols:
    """
    Description:
    Czytnik mapy symboli paczki syntetycznej. Mapę zapisuje skrypt na końcu budowy paczki, więc
    tak jak czytnik kodu odmawia, gdy paczki nie zbudowano — albo zbudowano ją, zanim skrypt
    zaczął budować mapę.

    Example args:
        (brak)

    Example result:
        CodeSymbols czytająca data/safe/code/symbols.json

    Raises:
        AssertionError: paczka syntetyczna nie ma mapy symboli
    """
    built = (SYNTHETIC_PACKAGE_DIR / "symbols.json").is_file()

    assert built, f"paczka syntetyczna nie ma mapy symboli — zbuduj ją: {BUILD_COMMAND}"

    return CodeSymbols(SYNTHETIC_PACKAGE_DIR)


def synthetic_code_texts() -> dict[str, str]:
    """
    Description:
    Treść każdego pliku zbudowanej paczki syntetycznej, po ścieżce względem `repo/` — tej samej,
    którą przyjmują narzędzia kodu. Odmawia, gdy paczki nie zbudowano.

    Example args:
        (brak)

    Example result:
        {"src/lib/Urzad/Szablony/RejestrSzablonow.php": "<?php\n\nnamespace Urzad\\Szablony;…", …}

    Raises:
        AssertionError: paczki syntetycznej nie zbudowano
    """
    repo  = SYNTHETIC_PACKAGE_DIR / "repo"
    built = repo.is_dir()

    assert built, f"brak zbudowanej paczki syntetycznej — zbuduj ją: {BUILD_COMMAND}"

    texts = {
        path.relative_to(repo).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(repo.rglob("*"))
        if path.is_file()
    }

    return texts


def synthetic_code_tools() -> list[AgentTool]:
    """
    Description:
    Sześć prawdziwych narzędzi kodu na paczce syntetycznej, w kolejności `TOOL_NAMES` grafów:
    opis projektu, szukanie ripgrepem, spis katalogu, odczyt pliku, odczyt symbolu i cytowanie.
    Do scenariuszy na żywym modelu, w których model ma dojść w kodzie do miejsca albo nie znaleźć
    niczego — atrapa szukania zawsze oddaje te same linie, więc sprawy „nigdzie” nie zagra.
    Odmawia, gdy paczki nie zbudowano.

    Example args:
        (brak)

    Example result:
        [DescribeCodeTool(…), FindCodeTextTool(…), ListCodeFilesTool(…), ReadCodeFileTool(…),
         ReadCodeSymbolTool(…), QuoteCodeTool(…)]

    Raises:
        AssertionError: paczki syntetycznej, jej metryczki albo mapy symboli nie zbudowano
    """
    package     = synthetic_code_package()
    description = synthetic_code_description()
    symbols     = synthetic_code_symbols()
    ripgrep     = RipgrepClient(timeout=SEARCH_TIMEOUT_SECONDS)

    tools: list[AgentTool] = [
        DescribeCodeTool(description=description),
        FindCodeTextTool(package=package, ripgrep=ripgrep, symbols=symbols),
        ListCodeFilesTool(package=package),
        ReadCodeFileTool(package=package),
        ReadCodeSymbolTool(package=package, symbols=symbols),
        QuoteCodeTool(package=package, description=description),
    ]

    return tools


def synthetic_code_cases(
    tool_name: str,  # np. "quote_code"
) -> list[dict[str, Any]]:
    """
    Description:
    Przypadki jednego narzędzia z zestawu syntetycznego: zapytanie w kształcie narzędzia
    i oczekiwany wynik. Zestaw leży w repo, więc czyta się go bez zbudowanej paczki.

    Example args:
        tool_name="quote_code"

    Example result:
        [{"id": "q01", "phenomenon": "cytowanie przyczyny tworzy źródło…",
          "query": {"path": "src/lib/…", "from_at": "…", "to_at": "…", "role": "cause"},
          "expected": {"source": True, "returns_text": False}}, …]
    """
    cases = json.loads(SYNTHETIC_CASES_FILE.read_text(encoding="utf-8"))

    return cases[tool_name]


def synthetic_absent_paths() -> list[str]:
    """
    Description:
    Ścieżki plików ze źródła aplikacji syntetycznej, których paczka nie może zawierać: cache,
    pliki z hasłami, biblioteki zewnętrzne, plik zminifikowany. Powód każdej stoi w zestawie.

    Example args:
        (brak)

    Example result:
        ["src/apps/frontend/cache/konfiguracja.php", "src/apps/frontend/config/app.yml", …]
    """
    cases = json.loads(SYNTHETIC_CASES_FILE.read_text(encoding="utf-8"))

    return [entry["path"] for entry in cases["absent_paths"]]


def line_of(
    package:  CodePackage,  # np. synthetic_code_package()
    path:     str,          # np. "src/lib/Urzad/Numeracja/GeneratorNumeru.php"
    fragment: str,          # np. "Brak sekwencji numeracji dla roku "
) -> int:
    """
    Description:
    Zamienia fragment linii zapisany w zestawie na numer linii, który test podaje narzędziu.
    Zestaw nie trzyma numerów, żeby dopisanie linii w pliku źródła nie przesuwało przypadków,
    a narzędzia kodu przyjmują numery — więc test wylicza numer tuż przed wywołaniem.

    Oddaje numer pierwszej linii pliku, w której stoi fragment, liczony od 1, jak w narzędziach
    kodu. Fragment w zestawie musi być na tyle charakterystyczny, żeby pierwsze trafienie
    w pliku było tym właściwym. Numer liczy się na zbudowanej paczce, nie na źródle: po zmianie
    źródła paczkę trzeba przebudować, inaczej numer wyjdzie ze starej wersji pliku.

    Example args:
        package=synthetic_code_package()
        path="src/lib/Urzad/Numeracja/GeneratorNumeru.php"
        fragment="Brak sekwencji numeracji dla roku "

    Example result:
        18

    Raises:
        AssertionError: fragmentu nie ma w pliku — zestaw i paczka się rozjechały
    """
    lines   = package.read_lines(path)
    numbers = [number for number, line in enumerate(lines, start=1) if fragment in line]

    assert numbers, f"fragmentu {fragment!r} nie ma w {path} — przebuduj paczkę: {BUILD_COMMAND}"

    return numbers[0]
