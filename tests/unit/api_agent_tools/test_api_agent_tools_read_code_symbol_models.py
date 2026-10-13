import pytest
from pydantic import ValidationError

from app.agent_tools.code.read_code_symbol import ReadCodeSymbolQuery


def test_a_name_alone_asks_for_the_whole_code() -> None:
    """Sprawdza, czy zapytanie z samą nazwą jest poprawne i nie niesie ścieżki, a spacje wokół
    nazwy znikają.

    Wyłapuje model zapytania, w którym ścieżka jest wymagana: model nie mógłby zapytać o funkcję,
    o której wie tylko, jak się nazywa — a nazwa ze spacją nie pasowałaby do żadnej definicji."""
    query = ReadCodeSymbolQuery(name="  nastepnyNumer ")

    assert (query.name, query.path) == ("nastepnyNumer", None)


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"path": "src/lib"},
        {"name": ""},
        {"name": "   "},
        {"name": "nastepnyNumer", "path": ""},
        {"name": "nastepnyNumer", "line": 13},
    ],
    ids=["nic", "sama ścieżka", "pusta nazwa", "same spacje", "pusta ścieżka", "nieznany argument"],
)
def test_a_query_without_a_name_or_with_an_unknown_argument_is_refused(arguments: dict) -> None:
    """Sprawdza, czy zapytanie bez nazwy, z nazwą pustą albo z samych spacji, z pustą ścieżką
    albo z argumentem spoza modelu kończy się wyjątkiem `ValidationError`.

    Wyłapuje zapytanie, które przechodzi z pustą nazwą: pasowałaby do niczego albo do wszystkiego,
    a model dostałby wynik, z którego nie wynika, że źle zapytał."""
    with pytest.raises(ValidationError):
        ReadCodeSymbolQuery(**arguments)
