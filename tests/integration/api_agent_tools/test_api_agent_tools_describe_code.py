"""
Description:
Test integracyjny narzędzia `describe_code` na paczce zbudowanej z aplikacji syntetycznej:
każde zapytanie z sekcji `describe_code` zestawu `data/safe/golden/code-synthetic.json` idzie
przez prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu; test
łańcucha z szukaniem wymaga programu ripgrep na hoście (`apt install ripgrep`).

| zjawisko z zestawu                          | oczekiwanie                                   |
|---------------------------------------------|-----------------------------------------------|
| opis projektu bez argumentów                | cały opis z pliku, bez komentarza redakcyjnego |
| metryczka paczki syntetycznej               | gałęzi nie ma, dzień budowy z metryczki       |
| argument wymyślony przez model              | błąd wracający do modelu                      |
| katalogi wymienione w opisie                | przyjmują je spis katalogu i szukanie         |

Paczkę, jej opis i zestaw dają helpery z `tests/helpers_code_package.py`; paczkę buduje się
skryptem przed testami. Opis aplikacji syntetycznej (`data/safe/code/project.md`) leży w repo.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowę nieznanego argumentu daje model
  zapytania, a model ma dostać błąd w miejscu wyniku.
- Opis aplikacji syntetycznej ma dwa zdania i pilnuje okablowania: że tekst dociera do modelu
  bez zmian, a jego katalogi istnieją w paczce. Czy opis pomaga w szukaniu, pokaże dopiero kod
  Dokusa (CLAUDE.md -> p. 23).
- Nowy przypadek dopisuje się w zestawie, nie tutaj.
"""

import json
from typing import Any

import pytest

from app.agent_graphs import suggest_solution
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools.base import is_error_json
from app.agent_tools.code.describe_code import DescribeCodeTool
from app.agent_tools.code.find_code_text import FindCodeTextQuery, FindCodeTextTool
from app.agent_tools.code.list_code_files import ListCodeFilesQuery, ListCodeFilesTool
from app.config import Settings
from app.engine_process.ripgrep import RipgrepClient
from tests.helpers_code_package import (
    SYNTHETIC_PACKAGE_DIR,
    synthetic_code_cases,
    synthetic_code_description,
    synthetic_code_package,
    synthetic_code_symbols,
)

CASES     = synthetic_code_cases("describe_code")
DESCRIBED = [case for case in CASES if not case["expected"].get("error")]
REFUSED   = [case for case in CASES if case["expected"].get("error")]

# Limit wywołań z konfiguracji domyślnej: jeden opis na sprawę.
LIMITS = {"describe_code": Settings(_env_file=None).agent_max_calls_describe_code}


async def _call(
    arguments: dict[str, Any],  # np. {} — narzędzie nie ma argumentów
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `describe_code` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i wpis w logu.

    Example args:
        arguments={}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"package_info": …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: describe_code; źródła: 0")]}
    """
    node  = RunToolsNode([DescribeCodeTool(description=synthetic_code_description())], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("describe_code", arguments)]},
    )

    return await node.run(state)


def test_the_set_has_a_description_to_read_and_a_call_to_refuse() -> None:
    """Sprawdza, czy sekcja `describe_code` zestawu ma przypadki obu rodzajów: opis do
    odczytania i wywołanie do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert DESCRIBED and REFUSED


@pytest.mark.parametrize("case", DESCRIBED, ids=lambda case: case["id"])
async def test_the_model_gets_the_whole_description_of_the_package(case: dict[str, Any]) -> None:
    """Sprawdza, czy model dostaje opis projektu z pliku `project.md` paczki syntetycznej
    w całości: z fragmentami, które zestaw każe mu zawierać, bez komentarza redakcyjnego z góry
    pliku i z każdym katalogiem, który zestaw wymienia.

    Wyłapuje narzędzie, które czyta inny plik, skraca opis albo przepuszcza komentarz pisany
    dla nas: model dostałby notatkę o sprawdzaniu ścieżek jako część opisu aplikacji."""
    expected = case["expected"]
    update   = await _call(case["query"])
    text     = update["messages"][0].content

    assert not is_error_json(text), text

    described = json.loads(text)["description"]
    on_disk   = (SYNTHETIC_PACKAGE_DIR / "project.md").read_text(encoding="utf-8")

    assert on_disk.rstrip().endswith(described)

    for fragment in expected["contains"]:
        assert fragment in described

    for fragment in expected["lacks"]:
        assert fragment not in described

    for path in expected["names_dirs"]:
        assert f"`{path}/`" in described


@pytest.mark.parametrize("case", DESCRIBED, ids=lambda case: case["id"])
async def test_the_model_gets_the_branch_and_the_build_day_of_the_package(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy obok opisu model dostaje metryczkę paczki syntetycznej: gałąź zapisaną
    w zestawie (paczka jej nie ma, więc `null`) i dzień budowy równy temu z pliku
    `manifest.json`.

    Wyłapuje narzędzie, które metryczkę zmyśla albo bierze skądinąd: model przypisałby kod
    z paczki do gałęzi, z której on nie pochodzi."""
    manifest = json.loads((SYNTHETIC_PACKAGE_DIR / "manifest.json").read_text(encoding="utf-8"))
    update   = await _call(case["query"])
    info     = json.loads(update["messages"][0].content)["package_info"]

    assert info == {"branch": case["expected"]["branch"], "built_on": manifest["built_on"]}


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_made_up_argument_goes_back_to_the_model_as_an_error(case: dict[str, Any]) -> None:
    """Sprawdza, czy wywołanie z argumentem, którego narzędzie nie ma (opis jednego katalogu),
    wraca do modelu jako błąd w miejscu wyniku.

    Wyłapuje narzędzie, które taki argument pomija i oddaje cały opis: model uznałby, że dostał
    opis wskazanego katalogu."""
    update = await _call(case["query"])

    assert is_error_json(update["messages"][0].content)


@pytest.mark.parametrize("case", DESCRIBED, ids=lambda case: case["id"])
async def test_the_description_never_adds_a_source(case: dict[str, Any]) -> None:
    """Sprawdza, czy odczyt opisu projektu nie dokłada niczego do listy źródeł odpowiedzi.

    Wyłapuje opis, który zaczął cytować: opis zawsze da się przeczytać, więc wariant wymagający
    źródeł oddawałby rozwiązanie w każdej sprawie, w której model zajrzał do opisu."""
    update = await _call(case["query"])

    assert "sources" not in update


@pytest.mark.parametrize("case", DESCRIBED, ids=lambda case: case["id"])
async def test_the_directories_of_the_description_are_taken_by_the_listing_and_the_search(
    case: dict[str, Any],
) -> None:
    """Sprawdza łańcuch narzędzi kodu na jednej paczce: każdy katalog wymieniony w opisie
    projektu da się spisać pod ścieżką z opisu, bez przeróbki, i podać szukaniu jako
    zawężenie — trafienia leżą wtedy tylko w nim, a słowo `function` znajduje się w więcej
    niż jednym z tych katalogów.

    Wyłapuje opis rozjechany z paczką albo ze ścieżkami liczonymi od innego katalogu niż
    w pozostałych narzędziach: model wziąłby z opisu katalog i dostał błąd od spisu."""
    package  = synthetic_code_package()
    listing  = ListCodeFilesTool(package=package)
    find     = FindCodeTextTool(
        package = package,
        ripgrep = RipgrepClient(timeout=10.0),
        symbols = synthetic_code_symbols(),
    )
    with_hit = 0

    for path in case["expected"]["names_dirs"]:
        listed = await listing.list_dir(ListCodeFilesQuery(path=path, depth=1))
        found  = await find.find(FindCodeTextQuery(exact="function", path=path))

        assert listed.entries, path
        assert all(line.path.startswith(f"{path}/") for line in found.lines), path

        # Katalog ze schematami tabel nie ma kodu, więc trafień w nim nie będzie.
        with_hit += bool(found.lines)

    assert with_hit > 1
