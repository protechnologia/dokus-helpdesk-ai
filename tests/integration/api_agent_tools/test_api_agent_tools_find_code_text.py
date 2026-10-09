"""
Description:
Test integracyjny narzędzia `find_code_text` na paczce zbudowanej z aplikacji syntetycznej: każde
zapytanie z sekcji `find_code_text` zestawu `data/safe/golden/code-synthetic.json` idzie przez
prawdziwy węzeł `run_tools`, tak jak wywołanie modelu. Bez stacku i bez modelu; wymaga programu
ripgrep na hoście (`apt install ripgrep`).

| zjawisko z zestawu                                   | oczekiwanie                          |
|------------------------------------------------------|--------------------------------------|
| komunikat rozkodowany, kilka brzmień, słowa, zawężenie | dokładnie linie z zestawu, z treścią |
| tekst, którego nie ma w paczce                       | pusta lista, nie błąd                |
| fraza i słowa w jednym wywołaniu                     | fraza pierwsza, każda linia raz      |
| więcej trafień niż limit                             | limit linii i licznik pominiętych    |
| ścieżka spoza paczki albo donikąd, puste zapytanie   | błąd wracający do modelu             |

Paczkę i zestaw dają helpery z `tests/helpers_code_package.py`; paczkę buduje się skryptem przed
testami.

O czym pamiętać przy zmianach:

- Zapytanie idzie przez węzeł, nie wprost do narzędzia: odmowa bywa dziełem modelu zapytania
  (brak frazy i słów) albo samego narzędzia (ścieżka), a model w obu przypadkach ma dostać to
  samo — błąd w miejscu wyniku.
- Zestaw trzyma miejsce jako ścieżkę i fragment linii; numer linii wylicza test na paczce.
- Nowy przypadek dopisuje się w zestawie, nie tutaj.
"""

import json
from typing import Any

import pytest

from app.agent_graphs import suggest_solution
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools.base import is_error_json
from app.agent_tools.code.find_code_text import MAX_LINES_PER_SEARCH, FindCodeTextTool
from app.config import Settings
from app.engine_process.ripgrep import RipgrepClient
from tests.helpers_code_package import line_of, synthetic_code_cases, synthetic_code_package

CASES      = synthetic_code_cases("find_code_text")
FOUND      = [case for case in CASES if isinstance(case.get("expected"), list)]
LABELLED   = [case for case in FOUND if any("matched_by" in place for place in case["expected"])]
OVER_LIMIT = [case for case in CASES if "expected_total" in case]
REFUSED    = [case for case in CASES if isinstance(case.get("expected"), dict)]

SETTINGS = Settings(_env_file=None)

# Limit wywołań z konfiguracji domyślnej; pojedyncze wywołanie i tak się w nim mieści.
LIMITS = {"find_code_text": SETTINGS.agent_max_calls_find_code_text}


async def _call(
    arguments: dict[str, Any],  # np. {"exact": "przekracza limit", "path": "src/lib"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje jedno wywołanie `find_code_text` przez prawdziwy węzeł `run_tools` na paczce
    syntetycznej i oddaje zmianę stanu: wiadomość dla modelu i wpis w logu.

    Example args:
        arguments={"exact": "przekracza limit"}

    Example result:
        {"messages": [ChatMessage(role="tool", call_id="call_1", content='{"lines": […], …}')],
         "log": [LogEntry(node="run_tools", message="wywołania: find_code_text; źródła: 0")]}
    """
    tool = FindCodeTextTool(
        package = synthetic_code_package(),
        ripgrep = RipgrepClient(timeout=SETTINGS.code_search_timeout_seconds),
    )
    node  = RunToolsNode([tool], LIMITS)
    state = suggest_solution.example_state().model_copy(
        update={"messages": [tool_call_turn("find_code_text", arguments)]},
    )

    return await node.run(state)


async def _result(
    arguments: dict[str, Any],  # np. {"exact": "przekracza limit"}
) -> dict[str, Any]:
    """
    Description:
    Wykonuje wywołanie i oddaje wynik narzędzia tak, jak czyta go model: JSON zamieniony na
    słownik. Odmawia, gdy model dostał błąd zamiast wyniku.

    Example args:
        arguments={"exact": "przekracza limit"}

    Example result:
        {"lines": [{"path": "src/lib/…/LimitZalacznika.php", "line": 27, "matched_by": "exact",
                    "text": "return 'Załącznik ' . $nazwa . …"}], "omitted_over_limit": 0}
    """
    update = await _call(arguments)
    text   = update["messages"][0].content

    assert not is_error_json(text), text

    return json.loads(text)


def test_the_set_has_cases_of_every_kind() -> None:
    """Sprawdza, czy sekcja `find_code_text` zestawu ma przypadki każdego rodzaju: z listą
    oczekiwanych linii, z etykietami, ponad limit i do odrzucenia.

    Wyłapuje zestaw po zmianie kształtu, w którym jedna z grup jest pusta: testy niżej nie
    uruchomiłyby się wtedy dla żadnego przypadku i wyglądały na zielone."""
    assert FOUND and LABELLED and OVER_LIMIT and REFUSED


@pytest.mark.parametrize("case", FOUND, ids=lambda case: case["id"])
async def test_a_search_finds_exactly_the_lines_of_the_set(case: dict[str, Any]) -> None:
    """Sprawdza, czy każde zapytanie z listą oczekiwanych miejsc oddaje dokładnie te linie: te
    same pliki i numery linii, z treścią zawierającą fragment zapisany w zestawie, bez linii
    pominiętych ponad limit. Pusta lista w zestawie znaczy pusty wynik.

    Wyłapuje szukanie, które gubi trafienie (komunikat zapisany w źródle sekwencjami, inny szyk
    słów), dokłada linie spoza paczki (cache, biblioteki zewnętrzne) albo zgłasza brak trafień
    jako błąd."""
    package  = synthetic_code_package()
    expected = {
        (place["path"], line_of(package, place["path"], place["fragment"])): place["fragment"]
        for place in case["expected"]
    }

    result = await _result(case["query"])
    found  = {(line["path"], line["line"]): line["text"] for line in result["lines"]}

    assert set(found)                   == set(expected)
    assert result["omitted_over_limit"] == 0

    for place, fragment in expected.items():
        assert fragment.strip() in found[place]


@pytest.mark.parametrize("case", LABELLED, ids=lambda case: case["id"])
async def test_phrase_matches_come_first_and_every_line_once(case: dict[str, Any]) -> None:
    """Sprawdza, czy przy frazie i słowach w jednym wywołaniu każda linia ma etykietę z zestawu,
    linie znalezione frazą stoją przed znalezionymi słowami, a linia pasująca do obu stoi raz,
    jako znaleziona frazą.

    Wyłapuje wynik, w którym ta sama linia wraca dwa razy, oraz kolejność mieszającą obie drogi:
    przy limicie długości trafienia po przepisanym komunikacie mogłyby wypaść za linie, które
    tylko zawierają te same słowa."""
    labels = {place["path"]: place["matched_by"] for place in case["expected"]}

    result = await _result(case["query"])
    order  = [line["matched_by"] for line in result["lines"]]

    assert {line["path"]: line["matched_by"] for line in result["lines"]} == labels
    assert order == sorted(order)  # „exact" stoi alfabetycznie przed „words"


@pytest.mark.parametrize("case", OVER_LIMIT, ids=lambda case: case["id"])
async def test_lines_over_the_limit_are_counted_not_shown(case: dict[str, Any]) -> None:
    """Sprawdza, czy zapytanie, do którego pasuje więcej linii, niż mieści wynik, oddaje dokładnie
    tyle linii, ile wynosi limit, wszystkie z plików zapisanych w zestawie, a resztę liczy
    w `omitted_over_limit`: pokazane i pominięte dają razem liczbę z zestawu.

    Wyłapuje wynik bez limitu, który przy częstej nazwie wkleja modelowi setki linii, oraz limit
    bez licznika: model nie odróżniłby wtedy „jest dwadzieścia trafień" od „pokazano dwadzieścia
    z pięciuset" i nie wiedziałby, że ma zawęzić szukanie."""
    result = await _result(case["query"])
    shown  = result["lines"]

    assert len(shown)                               == MAX_LINES_PER_SEARCH
    assert len(shown) + result["omitted_over_limit"] == case["expected_total"]
    assert {line["path"] for line in shown}         <= set(case["expected_files"])


@pytest.mark.parametrize("case", REFUSED, ids=lambda case: case["id"])
async def test_a_refused_search_goes_back_to_the_model_as_an_error(case: dict[str, Any]) -> None:
    """Sprawdza, czy dla każdego zapytania do odrzucenia z zestawu (ścieżka wychodząca poza
    paczkę, ścieżka, której nie ma, brak frazy i słów) model dostaje w miejscu wyniku błąd.

    Wyłapuje szukanie poza paczką przyjęte jak poprawne oraz odmowę, która przerywa przebieg,
    zamiast wrócić do modelu: sprawa z jedną pomyłką w ścieżce kończyłaby się błędem serwera."""
    update = await _call(case["query"])

    assert is_error_json(update["messages"][0].content)


@pytest.mark.parametrize("case", FOUND + OVER_LIMIT, ids=lambda case: case["id"])
async def test_a_search_never_adds_a_source(case: dict[str, Any]) -> None:
    """Sprawdza, czy żadne szukanie z zestawu, także takie, które znajduje linie i pokazuje ich
    treść, nie dokłada niczego do listy źródeł odpowiedzi.

    Wyłapuje szukanie, które zaczęło cytować: wariant wymagający źródeł oddałby wtedy
    rozwiązanie w sprawie, w której model tylko znalazł linię i niczego nie wskazał jako
    przyczyny."""
    update = await _call(case["query"])

    assert "sources" not in update
