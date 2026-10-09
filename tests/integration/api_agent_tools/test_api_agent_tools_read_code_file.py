"""
Description:
Test integracyjny narzędzia `read_code_file` na paczce zbudowanej z aplikacji syntetycznej: każde
zapytanie z sekcji `read_code_file` zestawu `data/safe/golden/code-synthetic.json` idzie przez
prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu; test łańcucha
z szukaniem wymaga programu ripgrep na hoście (`apt install ripgrep`).

| zjawisko z zestawu                                 | oczekiwanie                              |
|----------------------------------------------------|------------------------------------------|
| mały plik, litery rozkodowane                      | cały plik, oznaczony koniec pliku        |
| długi kontroler bez zakresu, zakres ponad limit    | limit linii i flaga urwania limitem      |
| zakres w środku pliku, od miejsca do końca         | dokładnie żądane linie, z numerami       |
| koniec zakresu za końcem pliku                     | linie do końca pliku, nie błąd           |
| ścieżka spoza paczki, katalog, początek za plikiem | błąd wracający do modelu                 |
| pliki, których paczka nie może zawierać            | błąd wracający do modelu                 |
| linia znaleziona przez `find_code_text`            | daje się odczytać i zacytować bez zmian  |

Paczkę i zestaw dają helpery z `tests/helpers_code_package.py`; paczkę buduje się skryptem przed
testami.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowa bywa dziełem modelu zapytania
  (odwrócony zakres) albo samego narzędzia (ścieżka, początek za plikiem), a model w obu
  przypadkach ma dostać to samo — błąd w miejscu wyniku.
- Zestaw trzyma miejsce jako fragment linii (`from_at`, `to_at`); numery wylicza test na paczce.
  Numer podany wprost (`from_line`, `to_line`) przechodzi bez zmian.
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
from app.agent_tools.code.quote_code import QuoteCodeQuery, QuoteCodeTool
from app.agent_tools.code.read_code_file import (
    MAX_LINES_PER_READ,
    ReadCodeFileQuery,
    ReadCodeFileTool,
)
from app.config import Settings
from app.engine_process.ripgrep import RipgrepClient
from tests.helpers_code_package import (
    line_of,
    synthetic_absent_paths,
    synthetic_code_cases,
    synthetic_code_package,
)

CASES   = synthetic_code_cases("read_code_file")
READ    = [case for case in CASES if not case["expected"].get("error")]
CUT     = [case for case in READ if case["expected"]["cut_by_limit"]]
REFUSED = [case for case in CASES if case["expected"].get("error")]

SETTINGS = Settings(_env_file=None)

# Limit wywołań z konfiguracji domyślnej; pojedyncze wywołanie i tak się w nim mieści.
LIMITS = {"read_code_file": SETTINGS.agent_max_calls_read_code_file}


def _arguments(
    query: dict[str, Any],  # np. {"path": "src/…", "from_at": "public function executeZamknij("}
) -> dict[str, Any]:
    """
    Description:
    Zamienia zapytanie z zestawu na argumenty narzędzia: fragmenty linii (`from_at`, `to_at`)
    stają się numerami linii, reszta przechodzi bez zmian.

    Example args:
        query={"path": "src/apps/frontend/modules/sprawy/actions/actions.class.php",
               "from_at": "public function executeZamknij(", "to_at": "Sprawa jest już zamknięta"}

    Example result:
        {"path": "src/apps/frontend/modules/sprawy/actions/actions.class.php", "from_line": 430,
         "to_line": 434}
    """
    package   = synthetic_code_package()
    arguments = {key: value for key, value in query.items() if not key.endswith("_at")}

    for anchor, argument in (("from_at", "from_line"), ("to_at", "to_line")):
        if anchor in query:
            arguments[argument] = line_of(package, query["path"], query[anchor])

    return arguments


async def _call(
    arguments: dict[str, Any],  # np. {"path": "src/web/js/_global/bledy.js"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `read_code_file` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i wpis w logu.

    Example args:
        arguments={"path": "src/web/js/_global/bledy.js"}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"path": "src/…", …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: read_code_file; źródła: 0")]}
    """
    node  = RunToolsNode([ReadCodeFileTool(package=synthetic_code_package())], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("read_code_file", arguments)]},
    )

    return await node.run(state)


async def _result(
    arguments: dict[str, Any],  # np. {"path": "src/web/js/_global/bledy.js"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje wywołanie i oddaje wynik narzędzia tak, jak czyta go model: JSON zamieniony na
    słownik. Odmawia, gdy model dostał błąd zamiast wyniku.

    Example args:
        arguments={"path": "src/web/js/_global/bledy.js"}

    Example result:
        {"path": "src/web/js/_global/bledy.js", "file_info": {"total_lines": 13},
         "requested": {"from_line": 1, "to_line": None},
         "returned": {"from_line": 1, "to_line": 13, "cut_by_limit": False, "end_of_file": True},
         "lines": [{"line": 1, "text": "…"}, …]}
    """
    update = await _call(arguments)
    text   = update["messages"][0].content

    assert not is_error_json(text), text

    return json.loads(text)


def test_the_set_has_cases_of_every_kind() -> None:
    """Sprawdza, czy sekcja `read_code_file` zestawu ma przypadki każdego rodzaju: odczyty do
    wykonania, wśród nich urwane limitem, oraz odczyty do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert READ and CUT and REFUSED


@pytest.mark.parametrize("case", READ, ids=lambda case: case["id"])
async def test_a_read_shows_what_the_set_expects(case: dict[str, Any]) -> None:
    """Sprawdza, czy każdy odczyt z zestawu oddaje linie, w których stoją fragmenty oczekiwane
    przez zestaw, nie oddaje fragmentów, których ma nie być, i oznacza zakres tak, jak zestaw
    zapisał: czy urwał go limit linii i czy kończy się na ostatniej linii pliku.

    Wyłapuje odczyt, który oddaje inny kawałek pliku niż żądany (litery zapisane w źródle
    sekwencjami, zakres przesunięty o linię), oraz flagi, które nie mówią prawdy o tym, czy
    model ma czytać dalej."""
    expected = case["expected"]
    result   = await _result(_arguments(case["query"]))
    text     = "\n".join(line["text"] for line in result["lines"])

    for fragment in expected.get("contains", []):
        assert fragment in text

    for fragment in expected.get("lacks", []):
        assert fragment not in text

    assert result["returned"]["cut_by_limit"] == expected["cut_by_limit"]
    assert result["returned"]["end_of_file"]  == expected["end_of_file"]


@pytest.mark.parametrize("case", READ, ids=lambda case: case["id"])
async def test_the_lines_are_the_lines_of_the_file_under_their_numbers(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy w każdym odczycie z zestawu każda oddana linia stoi pod swoim numerem
    z pliku w paczce i ma jego treść znak w znak, numery idą kolejno od początku oddanego
    zakresu do jego końca, a podana długość pliku jest prawdziwa.

    Wyłapuje numery rozjechane z plikiem: model cytuje fragment numerami z odczytu, więc źródło
    wskazywałoby inne linie niż te, które przeczytał."""
    arguments = _arguments(case["query"])
    in_file   = synthetic_code_package().read_lines(arguments["path"])

    result   = await _result(arguments)
    returned = result["returned"]

    assert [line["line"] for line in result["lines"]] == list(
        range(returned["from_line"], returned["to_line"] + 1),
    )
    assert result["file_info"]["total_lines"] == len(in_file)

    for line in result["lines"]:
        assert line["text"] == in_file[line["line"] - 1]


@pytest.mark.parametrize("case", CUT, ids=lambda case: case["id"])
async def test_a_read_cut_by_the_limit_can_be_continued(case: dict[str, Any]) -> None:
    """Sprawdza, czy odczyt urwany limitem oddaje dokładnie tyle linii, ile wynosi limit
    (`MAX_LINES_PER_READ`), a drugi odczyt, od linii następnej po ostatniej oddanej, zaczyna się
    właśnie od niej, czyli nie gubi żadnej linii i żadnej nie powtarza.

    Wyłapuje wynik bez limitu, który wkleja modelowi cały długi kontroler, oraz zakres oddany
    podany tak, że doczytanie reszty pliku pomija linię albo czyta ją drugi raz."""
    arguments = _arguments(case["query"])
    first     = await _result(arguments)
    next_line = first["returned"]["to_line"] + 1

    second = await _result({"path": arguments["path"], "from_line": next_line})

    assert len(first["lines"])              == MAX_LINES_PER_READ
    assert second["lines"][0]["line"]       == next_line
    assert second["requested"]["from_line"] == next_line


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_refused_read_goes_back_to_the_model_as_an_error(case: dict[str, Any]) -> None:
    """Sprawdza, czy dla każdego odczytu do odrzucenia z zestawu (ścieżka wychodząca poza paczkę,
    katalog, początek za końcem pliku, odwrócony zakres) model dostaje w miejscu wyniku błąd.

    Wyłapuje odczyt poza paczką przyjęty jak poprawny oraz odmowę, która przerywa przebieg,
    zamiast wrócić do modelu: sprawa z jedną pomyłką w ścieżce kończyłaby się błędem serwera."""
    update = await _call(_arguments(case["query"]))

    assert is_error_json(update["messages"][0].content)


@pytest.mark.parametrize("path", synthetic_absent_paths())
async def test_a_file_kept_out_of_the_package_cannot_be_read(path: str) -> None:
    """Sprawdza, czy odczyt każdego pliku, który leży w źródle aplikacji syntetycznej, ale nie
    może wejść do paczki (cache, plik z hasłami, biblioteka zewnętrzna, plik zminifikowany),
    kończy się błędem wracającym do modelu.

    Wyłapuje plik, który trafił do paczki mimo reguł, albo odczyt sięgający poza paczkę: model
    dostałby wtedy treść, której reguły paczki miały mu nie pokazać."""
    update = await _call({"path": path})

    assert is_error_json(update["messages"][0].content)


@pytest.mark.parametrize("case", READ, ids=lambda case: case["id"])
async def test_a_read_never_adds_a_source(case: dict[str, Any]) -> None:
    """Sprawdza, czy żaden odczyt z zestawu, także taki, który pokazuje linię z przyczyną, nie
    dokłada niczego do listy źródeł odpowiedzi.

    Wyłapuje odczyt, który zaczął cytować: plik zawsze da się przeczytać, więc wariant
    wymagający źródeł oddawałby rozwiązanie w każdej sprawie, w której model zajrzał do kodu
    i niczego nie wskazał jako przyczyny."""
    update = await _call(_arguments(case["query"]))

    assert "sources" not in update


async def test_a_line_found_by_the_search_can_be_read_and_then_quoted() -> None:
    """Sprawdza łańcuch trzech narzędzi kodu na jednej paczce: ścieżkę i numer linii z wyniku
    `find_code_text` da się podać `read_code_file` bez przeróbki, odczyt kilku linii wokół
    trafienia oddaje tę linię pod tym samym numerem i z tą samą treścią, a zakres, który odczyt
    oddał, `quote_code` przyjmuje jako przyczynę i robi z niego źródło.

    Wyłapuje rozjazd między narzędziami kodu: ścieżkę liczoną od innego katalogu albo linie
    numerowane inaczej. Model czytałby wtedy inne miejsce, niż wskazało mu szukanie, albo
    cytował linie, których odczyt nie pokazał."""
    package = synthetic_code_package()
    find    = FindCodeTextTool(package=package, ripgrep=RipgrepClient(timeout=10.0))
    read    = ReadCodeFileTool(package=package)
    quote   = QuoteCodeTool(package=package)

    found = await find.find(FindCodeTextQuery(exact="przekracza limit"))

    assert found.lines

    for hit in found.lines:
        # --- odczyt: trzy linie przed trafieniem i trzy po nim, w granicach pliku ---
        around = await read.read(
            ReadCodeFileQuery(path=hit.path, from_line=max(1, hit.line - 3), to_line=hit.line + 3),
        )
        [same] = [line for line in around.lines if line.line == hit.line]

        assert around.path       == hit.path
        assert same.text.strip() == hit.text

        # --- cytowanie: dokładnie ten zakres, który odczyt oddał ---
        [ref] = quote.cite(await quote.search(QuoteCodeQuery(
            path      = around.path,
            from_line = around.returned.from_line,
            to_line   = around.returned.to_line,
            role      = "cause",
        )))

        assert ref.key == (
            f"code:{hit.path}:{around.returned.from_line}-{around.returned.to_line}"
        )
