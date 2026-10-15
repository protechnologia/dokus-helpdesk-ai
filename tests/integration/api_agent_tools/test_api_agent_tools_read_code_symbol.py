"""
Description:
Test integracyjny narzędzia `read_code_symbol` na paczce zbudowanej z aplikacji syntetycznej:
każde zapytanie z sekcji `read_code_symbol` zestawu `data/safe/golden/code-synthetic.json` idzie
przez prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu; test
łańcucha z szukaniem wymaga programu ripgrep na hoście (`apt install ripgrep`).

| zjawisko z zestawu                                   | oczekiwanie                              |
|------------------------------------------------------|------------------------------------------|
| nazwa z plikiem, z katalogiem, jedyna w kodzie       | jedna definicja z jej liniami            |
| nazwa razem z klasą albo z obiektem                  | ta sama definicja co po nazwie z plikiem |
| klasa dłuższa niż limit linii                        | początek klasy i flaga urwania limitem   |
| ta sama nazwa akcji w trzech modułach                | trzech kandydatów, bez treści            |
| brak definicji, zła klasa, ścieżka spoza paczki      | błąd wracający do modelu, z podpowiedzią |
| linia znaleziona przez `find_code_text`              | jej funkcja daje się odczytać i zacytować |

Paczkę, jej mapę symboli i zestaw dają helpery z `tests/_helpers/synthetic_code/`; paczkę buduje
się skryptem przed testami.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowa bywa dziełem modelu zapytania
  (pusta nazwa) albo samego narzędzia (brak definicji, ścieżka), a model w obu przypadkach ma
  dostać to samo — błąd w miejscu wyniku.
- Test „każda definicja z miejscem" nie czyta zestawu: przechodzi po całej mapie symboli
  paczki, więc obejmuje też funkcje, których w zestawie nie ma.
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
from app.agent_tools.code.read_code_file import ReadCodeFileQuery, ReadCodeFileTool
from app.agent_tools.code.read_code_symbol import (
    MAX_LINES_PER_SYMBOL,
    ReadCodeSymbolQuery,
    ReadCodeSymbolTool,
)
from app.config import Settings
from app.engine_process.ripgrep import RipgrepClient
from tests._helpers.synthetic_code import (
    synthetic_code_cases,
    synthetic_code_description,
    synthetic_code_package,
    synthetic_code_symbols,
)

CASES      = synthetic_code_cases("read_code_symbol")
FOUND      = [case for case in CASES if "symbol" in case["expected"]]
CUT        = [case for case in FOUND if case["expected"]["cut_by_limit"]]
WITH_PLACE = [case for case in FOUND if set(":.") & set(case["query"]["name"])]
CANDIDATES = [case for case in CASES if "candidates" in case["expected"]]
REFUSED    = [case for case in CASES if case["expected"].get("error")]

SETTINGS = Settings(_env_file=None)

# Limit wywołań z konfiguracji domyślnej; pojedyncze wywołanie i tak się w nim mieści.
LIMITS = {"read_code_symbol": SETTINGS.agent_max_calls_read_code_symbol}

# Separator między miejscem a nazwą, którym model zapisuje definicję w każdym z języków.
SEPARATOR = {"php": "::", "js": "."}


def _tool() -> ReadCodeSymbolTool:
    """
    Description:
    Buduje narzędzie na paczce syntetycznej i jej mapie symboli.

    Example args:
        (brak)

    Example result:
        ReadCodeSymbolTool czytające definicje z data/safe/code
    """
    return ReadCodeSymbolTool(package=synthetic_code_package(), symbols=synthetic_code_symbols())


async def _call(
    arguments: dict[str, Any],  # np. {"name": "nastepnyNumer", "path": "src/lib/Urzad"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `read_code_symbol` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i wpis w logu.

    Example args:
        arguments={"name": "nastepnyNumer", "path": "src/lib/Urzad"}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"requested": …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: read_code_symbol; źródła: 0")]}
    """
    node  = RunToolsNode([_tool()], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("read_code_symbol", arguments)]},
    )

    return await node.run(state)


async def _result(
    arguments: dict[str, Any],  # np. {"name": "nastepnyNumer"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje wywołanie i oddaje wynik narzędzia tak, jak czyta go model: JSON zamieniony na
    słownik. Odmawia, gdy model dostał błąd zamiast wyniku.

    Example args:
        arguments={"name": "nastepnyNumer"}

    Example result:
        {"requested": {"name": "nastepnyNumer", "path": None},
         "symbol": {"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php", "name": "nastepnyNumer",
                    "scope": "GeneratorNumeru", "kind": "method", "from_line": 13, "to_line": 26},
         "returned": {"from_line": 13, "to_line": 26, "cut_by_limit": False},
         "lines": [{"line": 13, "text": "…"}, …], "candidates": [], "omitted_over_limit": 0}
    """
    update = await _call(arguments)
    text   = update["messages"][0].content

    assert not is_error_json(text), text

    return json.loads(text)


def test_the_set_has_cases_of_every_kind() -> None:
    """Sprawdza, czy sekcja `read_code_symbol` zestawu ma przypadki każdego rodzaju: z jedną
    definicją, urwane limitem, z nazwą podaną razem z miejscem, z kandydatami i do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert FOUND and CUT and WITH_PLACE and CANDIDATES and REFUSED


@pytest.mark.parametrize("case", FOUND, ids=lambda case: case["id"])
async def test_a_name_gives_the_definition_the_set_expects(case: dict[str, Any]) -> None:
    """Sprawdza, czy każde zapytanie z jedną oczekiwaną definicją oddaje właśnie ją — ten plik,
    to miejsce i ten rodzaj — z treścią, która zawiera fragmenty zapisane w zestawie, nie zawiera
    fragmentów sąsiedniej definicji i ma flagę urwania zgodną z zestawem, bez listy kandydatów.

    Wyłapuje odczyt, który oddaje akcję innego modułu, zakres obejmujący sąsiednią funkcję albo
    kandydatów tam, gdzie nazwa z miejscem wskazuje jedną definicję."""
    expected = case["expected"]
    result   = await _result(case["query"])
    text     = "\n".join(line["text"] for line in result["lines"])
    symbol   = result["symbol"]

    assert {key: symbol[key] for key in ("path", "scope", "kind")} == expected["symbol"]
    assert result["returned"]["cut_by_limit"] is expected["cut_by_limit"]
    assert (result["candidates"], result["omitted_over_limit"]) == ([], 0)

    for fragment in expected["contains"]:
        assert fragment in text, fragment

    for fragment in expected.get("lacks", []):
        assert fragment not in text, fragment


@pytest.mark.parametrize("case", FOUND, ids=lambda case: case["id"])
async def test_the_lines_are_the_lines_of_the_file_under_their_numbers(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy każda oddana linia ma treść tej linii pliku w paczce, której numer niesie,
    a oddany zakres zaczyna się w pierwszej linii definicji i kończy tam, gdzie mówi wynik.

    Wyłapuje numery przesunięte względem pliku: model cytowałby potem przeczytany fragment pod
    numerami, pod którymi w pliku stoi co innego."""
    result  = await _result(case["query"])
    in_file = synthetic_code_package().read_lines(result["symbol"]["path"])
    numbers = [line["line"] for line in result["lines"]]

    assert numbers == list(range(result["symbol"]["from_line"], result["returned"]["to_line"] + 1))

    for line in result["lines"]:
        assert line["text"] == in_file[line["line"] - 1]


@pytest.mark.parametrize("case", CUT, ids=lambda case: case["id"])
async def test_a_definition_cut_by_the_limit_can_be_continued_by_the_file_read(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy definicja urwana limitem oddaje dokładnie tyle linii, ile wynosi limit
    (`MAX_LINES_PER_SYMBOL`), a odczyt pliku od następnej linii do ostatniej linii definicji
    zaczyna się i kończy tam, gdzie mówi wynik.

    Wyłapuje urwanie, po którym nie da się doczytać reszty: opis narzędzia odsyła model do
    `read_code_file` z numerami z wyniku, więc muszą to być numery tego samego pliku."""
    first     = await _result(case["query"])
    next_line = first["returned"]["to_line"] + 1
    last_line = first["symbol"]["to_line"]

    rest = await ReadCodeFileTool(package=synthetic_code_package()).read(
        ReadCodeFileQuery(path=first["symbol"]["path"], from_line=next_line, to_line=last_line),
    )

    assert len(first["lines"]) == MAX_LINES_PER_SYMBOL
    assert (rest.returned.from_line, rest.returned.to_line) == (next_line, last_line)


@pytest.mark.parametrize("case", CANDIDATES, ids=lambda case: case["id"])
async def test_a_name_with_several_definitions_gives_candidates_without_any_line(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy nazwa wskazująca kilka definicji oddaje kandydatów z zestawu, w tej samej
    kolejności, każdego z plikiem, miejscem i liniami, a nie oddaje definicji, zakresu ani treści.

    Wyłapuje narzędzie, które przy kilku definicjach wybiera za model: akcję o tej samej nazwie
    mają trzy moduły i tylko model wie, o który chodzi w zgłoszeniu."""
    result = await _result(case["query"])

    assert (result["symbol"], result["returned"], result["lines"]) == (None, None, [])
    assert [[c["path"], c["scope"]] for c in result["candidates"]] == case["expected"]["candidates"]
    assert all(c["from_line"] <= c["to_line"] for c in result["candidates"])


@pytest.mark.parametrize("case", CANDIDATES, ids=lambda case: case["id"])
async def test_every_candidate_can_be_read_by_narrowing_the_path_to_its_file(
    case: dict[str, Any],
) -> None:
    """Sprawdza drugi krok po liście kandydatów: to samo zapytanie ze ścieżką zawężoną do pliku
    kandydata oddaje już jedną definicję, równą temu kandydatowi, z treścią.

    Wyłapuje listę kandydatów, z której nie ma wyjścia: ścieżkę w innej postaci niż ta, którą
    narzędzie przyjmuje, albo zawężenie, które nadal daje kilka definicji."""
    result = await _result(case["query"])

    for candidate in result["candidates"]:
        narrowed = await _result({"name": case["query"]["name"], "path": candidate["path"]})

        assert narrowed["symbol"] == candidate
        assert narrowed["lines"]


async def test_every_definition_with_a_place_reads_the_same_by_place_and_by_file() -> None:
    """Sprawdza każdą funkcję i metodę paczki syntetycznej, która leży w klasie albo w obiekcie:
    nazwa podana razem z miejscem (`Klasa::metoda` w PHP, `obiekt.funkcja` w JS), bez ścieżki,
    oddaje tę samą definicję i te same linie, co sama nazwa zawężona do pliku.

    Wyłapuje zapis z miejscem działający tylko dla przykładów z opisu narzędzia: test nie czyta
    zestawu, tylko całą mapę symboli, więc obejmuje każdą akcję i każdy handler paczki."""
    symbol_map = synthetic_code_symbols().read()
    tool       = _tool()
    checked    = 0

    for path, symbols in symbol_map.files.items():
        for symbol in symbols:
            if symbol.scope is None or symbol.kind == "class":
                continue

            with_place = f"{symbol.scope}{SEPARATOR[path.rsplit('.', 1)[-1]]}{symbol.name}"
            by_place   = await tool.read(ReadCodeSymbolQuery(name=with_place))
            by_file    = await tool.read(ReadCodeSymbolQuery(name=symbol.name, path=path))
            checked   += 1

            assert by_place.symbol is not None, with_place
            assert (by_place.symbol.path, by_place.symbol.from_line) == (path, symbol.from_line)
            assert by_place.symbol == by_file.symbol, with_place
            assert by_place.lines  == by_file.lines, with_place

    # Paczka ma kilkadziesiąt takich definicji; zero znaczyłoby, że test niczego nie sprawdził.
    assert checked > 40


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_refused_read_goes_back_to_the_model_as_an_error_that_says_why(
    case: dict[str, Any],
) -> None:
    """Sprawdza, czy dla każdego odczytu do odrzucenia z zestawu (nazwa, której nie ma, metoda
    poza wskazanym katalogiem, klasa bez takiej metody, ścieżka spoza paczki) model dostaje
    w miejscu wyniku błąd, a komunikat zawiera podpowiedź zapisaną w zestawie.

    Wyłapuje odmowę, która przerywa przebieg, zamiast wrócić do modelu, oraz jeden komunikat na
    wszystkie przypadki: po nim model nie wiedziałby, czy poszerzyć ścieżkę, czy szukać tekstem."""
    update = await _call(case["query"])
    text   = update["messages"][0].content

    assert is_error_json(text)
    assert case["expected"]["says"] in json.loads(text)["error"]


@pytest.mark.parametrize("case", [*FOUND, *CANDIDATES], ids=lambda case: case["id"])
async def test_a_symbol_read_never_adds_a_source(case: dict[str, Any]) -> None:
    """Sprawdza, czy żaden odczyt symbolu z zestawu, także taki, który pokazuje funkcję
    z przyczyną, nie dokłada niczego do listy źródeł odpowiedzi.

    Wyłapuje odczyt, który zaczął cytować: funkcję zawsze da się przeczytać, więc wariant
    wymagający źródeł oddawałby rozwiązanie w każdej sprawie, w której model zajrzał do kodu
    i niczego nie wskazał jako przyczyny."""
    update = await _call(case["query"])

    assert "sources" not in update


async def test_the_function_of_a_found_line_can_be_read_and_then_quoted() -> None:
    """Sprawdza łańcuch trzech narzędzi kodu na jednej paczce: nazwę funkcji i ścieżkę z wyniku
    `find_code_text` da się podać `read_code_symbol` bez przeróbki, odczytana definicja obejmuje
    znalezioną linię pod tym samym numerem i z tą samą treścią, a jej zakres `quote_code`
    przyjmuje jako przyczynę i robi z niego źródło.

    Wyłapuje rozjazd między szukaniem a odczytem symbolu: nazwę przy linii, której odczyt nie
    zna, albo funkcję, w której znalezionej linii nie ma. Model czytałby wtedy inną funkcję niż
    ta, którą wskazało mu szukanie."""
    package = synthetic_code_package()
    find    = FindCodeTextTool(
        package = package,
        ripgrep = RipgrepClient(timeout=10.0),
        symbols = synthetic_code_symbols(),
    )
    quote   = QuoteCodeTool(package=package, description=synthetic_code_description())

    found = await find.find(FindCodeTextQuery(exact="przekracza limit"))
    named = [hit for hit in found.lines if hit.symbol]

    assert named and len(named) == len(found.lines)

    for hit in named:
        # --- odczyt: nazwa funkcji i ścieżka dokładnie w brzmieniu z wyniku szukania ---
        read   = await _tool().read(ReadCodeSymbolQuery(name=hit.symbol, path=hit.path))
        [same] = [line for line in read.lines if line.line == hit.line]

        assert read.symbol.path  == hit.path
        assert same.text.strip() == hit.text

        # --- cytowanie: dokładnie ten zakres, który odczyt oddał ---
        [ref] = quote.cite(await quote.search(QuoteCodeQuery(
            path      = read.symbol.path,
            from_line = read.returned.from_line,
            to_line   = read.returned.to_line,
            role      = "cause",
        )))

        assert ref.key == (
            f"code:{hit.path}:{read.returned.from_line}-{read.returned.to_line}"
        )
