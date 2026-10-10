"""
Description:
Test integracyjny narzędzia `list_code_files` na paczce zbudowanej z aplikacji syntetycznej:
każde zapytanie z sekcji `list_code_files` zestawu `data/safe/golden/code-synthetic.json` idzie
przez prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu; test
łańcucha z szukaniem wymaga programu ripgrep na hoście (`apt install ripgrep`).

| zjawisko z zestawu                                   | oczekiwanie                              |
|------------------------------------------------------|------------------------------------------|
| katalog obok biblioteki zewnętrznej, cache, hasła    | pozycje paczki są, plików spoza niej nie |
| bez argumentów                                       | dwa poziomy od katalogu głównego kodu    |
| dwa poziomy, głębokość większa niż katalog           | podkatalogi ze swoimi plikami, bez błędu |
| katalog zapisany przez `..`                          | ścieżka wraca w jednej postaci           |
| brak katalogu, plik, wyjście poza paczkę, głębokość 0 | błąd wracający do modelu                |
| pliki, których paczka nie może zawierać              | nie ma ich w spisie całego kodu          |
| pozycje spisu                                        | przyjmują je odczyt pliku i szukanie     |

Paczkę i zestaw dają helpery z `tests/helpers_code_package.py`; paczkę buduje się skryptem przed
testami.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowa bywa dziełem modelu zapytania
  (głębokość zero) albo samego narzędzia (ścieżka), a model w obu przypadkach ma dostać to samo —
  błąd w miejscu wyniku.
- Paczka syntetyczna ma kilkadziesiąt pozycji, więc limitu 200 pozycji nie osiąga. Ucięcie
  głębokości i katalog ponad limit sprawdzają testy jednostkowe części wspólnej i narzędzia.
- Nowy przypadek dopisuje się w zestawie, nie tutaj.
"""

import json
from typing import Any

import pytest

from app.agent_graphs import suggest_solution
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools.base import is_error_json
from app.agent_tools.code.find_code_text import FindCodeTextQuery, FindCodeTextTool
from app.agent_tools.code.list_code_files import ListCodeFilesQuery, ListCodeFilesTool
from app.agent_tools.code.read_code_file import ReadCodeFileQuery, ReadCodeFileTool
from app.config import Settings
from app.engine_process.ripgrep import RipgrepClient
from tests.helpers_code_package import (
    synthetic_absent_paths,
    synthetic_code_cases,
    synthetic_code_package,
)

CASES   = synthetic_code_cases("list_code_files")
LISTED  = [case for case in CASES if not case["expected"].get("error")]
DEEPER  = [case for case in LISTED if case["expected"]["has_more_depth"]]
REFUSED = [case for case in CASES if case["expected"].get("error")]

SETTINGS = Settings(_env_file=None)

# Limit wywołań z konfiguracji domyślnej; pojedyncze wywołanie i tak się w nim mieści.
LIMITS = {"list_code_files": SETTINGS.agent_max_calls_list_code_files}

# Głębokość większa niż ma jakikolwiek katalog paczki syntetycznej: spis całego kodu.
WHOLE_TREE = 50


async def _call(
    arguments: dict[str, Any],  # np. {"path": "src/web/js", "depth": 1}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `list_code_files` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i wpis w logu.

    Example args:
        arguments={"path": "src/web/js", "depth": 1}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"path": "src/…", …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: list_code_files; źródła: 0")]}
    """
    node  = RunToolsNode([ListCodeFilesTool(package=synthetic_code_package())], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("list_code_files", arguments)]},
    )

    return await node.run(state)


async def _result(
    arguments: dict[str, Any],  # np. {"path": "src/web/js", "depth": 1}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje wywołanie i oddaje wynik narzędzia tak, jak czyta go model: JSON zamieniony na
    słownik. Odmawia, gdy model dostał błąd zamiast wyniku.

    Example args:
        arguments={"path": "src/web/js", "depth": 1}

    Example result:
        {"path": "src/web/js", "dir_info": {"total_depth": 2}, "requested": {"depth": 1},
         "returned": {"depth": 1, "depth_cut_by_limit": False, "has_more_depth": True,
                      "omitted_over_limit": 0},
         "entries": [{"path": "src/web/js/_global", "kind": "dir"}, …]}
    """
    update = await _call(arguments)
    text   = update["messages"][0].content

    assert not is_error_json(text), text

    return json.loads(text)


def test_the_set_has_cases_of_every_kind() -> None:
    """Sprawdza, czy sekcja `list_code_files` zestawu ma przypadki każdego rodzaju: spisy do
    wykonania, wśród nich takie, pod którymi katalog sięga głębiej, i takie, które pokazują
    wszystko, oraz spisy do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert LISTED and DEEPER and REFUSED
    assert len(DEEPER) < len(LISTED)


@pytest.mark.parametrize("case", LISTED, ids=lambda case: case["id"])
async def test_a_listing_shows_what_the_set_expects(case: dict[str, Any]) -> None:
    """Sprawdza, czy każdy spis z zestawu zawiera pozycje oczekiwane przez zestaw, nie zawiera
    tych, których ma nie być (biblioteka zewnętrzna, cache, plik z hasłem, plik zminifikowany,
    pozycje z głębszego poziomu), i podaje ścieżkę katalogu, oddaną głębokość oraz to, czy
    katalog sięga głębiej, tak jak zestaw zapisał.

    Wyłapuje spis, który pokazuje pliki spoza paczki albo inny poziom niż żądany, oraz sygnał
    głębokości, który nie mówi prawdy o tym, czy model ma szukać głębiej."""
    expected = case["expected"]
    result   = await _result(case["query"])
    paths    = [entry["path"] for entry in result["entries"]]

    for path in expected["includes"]:
        assert path in paths

    for path in expected["lacks"]:
        assert path not in paths

    assert result["path"]                       == expected["path"]
    assert result["returned"]["depth"]          == expected["depth"]
    assert result["returned"]["has_more_depth"] == expected["has_more_depth"]


@pytest.mark.parametrize("case", LISTED, ids=lambda case: case["id"])
async def test_every_entry_is_what_the_package_has_under_its_path(case: dict[str, Any]) -> None:
    """Sprawdza, czy w każdym spisie z zestawu każda pozycja oznaczona jako plik jest plikiem
    paczki, a każda oznaczona jako katalog jest jej katalogiem, każda leży pod spisanym
    katalogiem nie głębiej, niż wynosi oddana głębokość, i żadna nie stoi dwa razy. Limit
    pozycji niczego przy tym nie zabiera, bo paczka syntetyczna jest na to za mała.

    Wyłapuje pozycję z pomylonym rodzajem albo ze ścieżką, której w paczce nie ma: model
    podałby katalog odczytowi pliku albo plik szukaniu i dostał błąd zamiast wyniku."""
    result = await _result(case["query"])
    repo   = synthetic_code_package().repo_dir()
    prefix = "" if result["path"] == "." else f"{result['path']}/"
    paths  = [entry["path"] for entry in result["entries"]]

    assert len(paths) == len(set(paths))
    assert result["returned"]["depth_cut_by_limit"] is False
    assert result["returned"]["omitted_over_limit"] == 0

    for entry in result["entries"]:
        below = entry["path"].removeprefix(prefix)

        assert entry["path"].startswith(prefix)
        assert below.count("/") < result["returned"]["depth"]
        assert (repo / entry["path"]).is_dir()  == (entry["kind"] == "dir")
        assert (repo / entry["path"]).is_file() == (entry["kind"] == "file")


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_refused_listing_goes_back_to_the_model_as_an_error(case: dict[str, Any]) -> None:
    """Sprawdza, czy dla każdego spisu do odrzucenia z zestawu (katalog, którego nie ma, ścieżka
    pliku, ścieżka wychodząca poza paczkę, głębokość zero) model dostaje w miejscu wyniku błąd.

    Wyłapuje spis katalogu spoza paczki przyjęty jak poprawny oraz odmowę, która przerywa
    przebieg, zamiast wrócić do modelu: sprawa z jedną pomyłką w ścieżce kończyłaby się błędem
    serwera."""
    update = await _call(case["query"])

    assert is_error_json(update["messages"][0].content)


async def test_the_whole_code_is_listed_without_the_files_kept_out_of_the_package() -> None:
    """Sprawdza, czy spis całego kodu, od katalogu głównego na pełną głębokość, wymienia
    dokładnie te pliki, które paczka ma na dysku, i żadnego z plików, które leżą w źródle
    aplikacji syntetycznej, ale nie mogą wejść do paczki — ani katalogów, w których one leżą.

    Wyłapuje spis, który gubi pliki albo dokłada cudze: plik z hasłem albo biblioteka zewnętrzna
    w spisie znaczyłyby, że trafiły do paczki mimo reguł, a brak pliku — że model nie znajdzie
    spisem czegoś, co potrafi odczytać."""
    package = synthetic_code_package()
    result  = await _result({"depth": WHOLE_TREE})
    paths   = [entry["path"] for entry in result["entries"]]
    files   = [entry["path"] for entry in result["entries"] if entry["kind"] == "file"]

    assert sorted(files) == package.list_files(".")
    assert result["returned"]["has_more_depth"] is False
    assert result["returned"]["depth"] == result["dir_info"]["total_depth"]

    for absent in synthetic_absent_paths():
        assert absent not in paths

    for excluded_dir in ("src/apps/frontend/cache", "src/lib/vendor", "src/web/js/_vendor"):
        assert excluded_dir not in paths


@pytest.mark.parametrize("case", LISTED, ids=lambda case: case["id"])
async def test_a_listing_never_adds_a_source(case: dict[str, Any]) -> None:
    """Sprawdza, czy żaden spis z zestawu nie dokłada niczego do listy źródeł odpowiedzi.

    Wyłapuje spis, który zaczął cytować: katalog zawsze da się obejrzeć, więc wariant
    wymagający źródeł oddawałby rozwiązanie w każdej sprawie, w której model rozejrzał się po
    kodzie i niczego nie wskazał jako przyczyny."""
    update = await _call(case["query"])

    assert "sources" not in update


async def test_the_listed_paths_are_taken_by_the_reading_and_by_the_search() -> None:
    """Sprawdza łańcuch narzędzi kodu na jednej paczce: każdy plik ze spisu katalogu
    `src/lib/Urzad/Wysylka` da się odczytać pod ścieżką ze spisu, bez przeróbki, a katalog ze
    spisu da się podać szukaniu jako zawężenie — trafienia leżą wtedy tylko w nim.

    Wyłapuje rozjazd między narzędziami kodu: ścieżkę ze spisu liczoną od innego katalogu niż
    ta, którą przyjmują odczyt i szukanie. Model musiałby wtedy zgadywać, jak przerobić
    pozycję spisu, zanim poda ją dalej."""
    package = synthetic_code_package()
    listing = await ListCodeFilesTool(package=package).list_dir(
        ListCodeFilesQuery(path="src/lib/Urzad/Wysylka", depth=2),
    )
    read = ReadCodeFileTool(package=package)
    find = FindCodeTextTool(package=package, ripgrep=RipgrepClient(timeout=10.0))

    files = [entry.path for entry in listing.entries if entry.kind == "file"]
    dirs  = [entry.path for entry in listing.entries if entry.kind == "dir"]

    assert files and dirs

    # --- odczyt: plik pod ścieżką ze spisu ---
    for path in files:
        assert (await read.read(ReadCodeFileQuery(path=path, to_line=1))).path == path

    # --- szukanie: katalog ze spisu jako zawężenie ---
    for path in dirs:
        found = await find.find(FindCodeTextQuery(exact="function", path=path))

        assert found.lines
        assert all(line.path.startswith(f"{path}/") for line in found.lines)
