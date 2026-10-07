"""
Description:
Test integracyjny narzędzia `quote_code` na paczce zbudowanej z aplikacji syntetycznej: każde
zapytanie z sekcji `quote_code` zestawu `data/safe/golden/code-synthetic.json` idzie przez
prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu.

| zjawisko z zestawu                         | oczekiwanie                              |
|--------------------------------------------|------------------------------------------|
| cytowanie przyczyny                        | potwierdzenie bez treści i jedno źródło  |
| cytowanie wykluczenia                      | potwierdzenie bez treści, bez źródła     |
| cytowanie bez roli                         | błąd wracający do modelu                 |
| fragment dłuższy niż limit cytowania       | błąd wracający do modelu                 |
| ścieżka wychodząca poza paczkę             | błąd wracający do modelu                 |

Paczkę i zestaw dają helpery z `tests/helpers_code_package.py`; paczkę buduje się skryptem przed
testami.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowa bywa dziełem modelu zapytania
  (brak roli, za długi fragment) albo samego narzędzia (ścieżka), a model w obu przypadkach ma
  dostać to samo — błąd w miejscu wyniku.
- Zestaw trzyma miejsce jako fragment linii (`from_at`, `to_at`); numery wylicza test na paczce.
- Nowy przypadek dopisuje się w zestawie, nie tutaj.
"""

from typing import Any

import pytest

from app.agent_graphs import suggest_solution
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools.base import is_error_json
from app.agent_tools.code.quote_code import QuoteCodeTool
from app.config import Settings
from tests.helpers_code_package import line_of, synthetic_code_cases, synthetic_code_package

CASES    = synthetic_code_cases("quote_code")
ACCEPTED = [case for case in CASES if not case["expected"].get("error")]
REFUSED  = [case for case in CASES if case["expected"].get("error")]

# Limit wywołań z konfiguracji domyślnej; pojedyncze wywołanie i tak się w nim mieści.
LIMITS = {"quote_code": Settings(_env_file=None).agent_max_calls_quote_code}


def _arguments(
    query: dict[str, Any],  # np. {"path": "src/…", "from_at": "…", "to_at": "…", "role": "cause"}
) -> dict[str, Any]:
    """
    Description:
    Zamienia zapytanie z zestawu na argumenty narzędzia: fragmenty linii (`from_at`, `to_at`)
    stają się numerami linii, reszta przechodzi bez zmian.

    Example args:
        query={"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php",
               "from_at": "if (!$sekwencja) {", "to_at": "Brak sekwencji numeracji dla roku ",
               "role": "cause"}

    Example result:
        {"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php", "from_line": 17, "to_line": 18,
         "role": "cause"}
    """
    package   = synthetic_code_package()
    arguments = {key: value for key, value in query.items() if not key.endswith("_at")}

    for anchor, argument in (("from_at", "from_line"), ("to_at", "to_line")):
        if anchor in query:
            arguments[argument] = line_of(package, query["path"], query[anchor])

    return arguments


async def _call(
    arguments: dict[str, Any],  # np. {"path": "src/…", "from_line": 17, "to_line": 18, …}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `quote_code` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i — jeśli powstały — źródła.

    Example args:
        arguments={"path": "src/lib/Urzad/Numeracja/GeneratorNumeru.php", "from_line": 17,
                   "to_line": 18, "role": "cause"}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"path": "src/…", …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: quote_code; źródła: 1")],
         "sources": [SourceRef(source="code", item_id="src/…:17-18", …)]}
    """
    node  = RunToolsNode([QuoteCodeTool(package=synthetic_code_package())], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("quote_code", arguments)]},
    )

    return await node.run(state)


def test_the_set_has_quotes_to_accept_and_to_refuse() -> None:
    """Sprawdza, czy sekcja `quote_code` zestawu ma przypadki obu rodzajów: cytowania do przyjęcia
    i cytowania do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert ACCEPTED and REFUSED


@pytest.mark.parametrize("case", ACCEPTED, ids=lambda case: case["id"])
async def test_an_accepted_quote_is_confirmed_without_the_code(case: dict[str, Any]) -> None:
    """Sprawdza, czy dla każdego cytowania do przyjęcia z zestawu model dostaje potwierdzenie,
    a nie błąd, i czy w potwierdzeniu nie ma fragmentów linii, na które cytowanie wskazuje.

    Wyłapuje cytowanie odrzucone mimo poprawnej ścieżki i zakresu oraz cytowanie, które oddaje
    treść kodu: model używałby go wtedy zamiast odczytu."""
    query  = case["query"]
    update = await _call(_arguments(query))
    text   = update["messages"][0].content

    assert not is_error_json(text)
    assert case["expected"]["returns_text"] is False
    assert query["from_at"] not in text
    assert query["to_at"] not in text


@pytest.mark.parametrize("case", ACCEPTED, ids=lambda case: case["id"])
async def test_only_a_cause_reaches_the_sources(case: dict[str, Any]) -> None:
    """Sprawdza, czy cytowanie z zestawu dokłada źródło dokładnie wtedy, gdy zestaw tego oczekuje:
    przyczyna daje jedno źródło z materiałem „code", ścieżką i zakresem linii w kluczu,
    a miejsce wykluczone nie daje żadnego.

    Wyłapuje źródło powstające z każdej roli albo z żadnej: odpowiedź powoływałaby się na kod,
    który model wykluczył, albo wracałaby bez źródła mimo wskazanej przyczyny."""
    arguments = _arguments(case["query"])
    update    = await _call(arguments)
    keys      = [ref.key for ref in update.get("sources", [])]

    expected = (
        [f"code:{arguments['path']}:{arguments['from_line']}-{arguments['to_line']}"]
        if case["expected"]["source"]
        else []
    )

    assert keys == expected


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_refused_quote_goes_back_to_the_model_as_an_error(case: dict[str, Any]) -> None:
    """Sprawdza, czy dla każdego cytowania do odrzucenia z zestawu (bez roli, dłuższego niż limit,
    ze ścieżką spoza paczki) model dostaje w miejscu wyniku błąd, a lista źródeł się nie zmienia.

    Wyłapuje cytowanie przyjęte mimo wady oraz odmowę, która przerywa przebieg, zamiast wrócić do
    modelu: sprawa z jedną pomyłką w cytowaniu kończyłaby się błędem serwera."""
    update = await _call(_arguments(case["query"]))

    assert is_error_json(update["messages"][0].content)
    assert "sources" not in update
