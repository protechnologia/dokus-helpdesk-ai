import pytest
from pydantic import ValidationError

from app.agent_tools.code.describe_code import DescribeCodeQuery, DescribeCodeResult
from app.core_model.code.code_package_info import CodePackageInfo

INFO = CodePackageInfo(branch=None, built_on="2026-10-07")


def test_the_query_has_no_arguments() -> None:
    """Sprawdza, czy zapytanie bez argumentów jest poprawne i czy model zapytania nie ma żadnego
    pola.

    Wyłapuje argument dopisany do zapytania: opis projektu jest jeden dla całego kodu i wraca
    w całości, więc model nie ma czego wybierać."""
    assert DescribeCodeQuery().model_dump() == {}


@pytest.mark.parametrize(
    "arguments",
    [{"path": "src/lib"}, {"section": "Baza danych"}],
    ids=["katalog", "sekcja"],
)
def test_an_argument_made_up_by_the_model_is_refused(arguments: dict) -> None:
    """Sprawdza, czy zapytanie z argumentem spoza schematu (`path`, `section`) kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje model zapytania, który taki argument po cichu pomija: model prosiłby o opis jednego
    katalogu i dostawał cały, przekonany, że dostał wycinek."""
    with pytest.raises(ValidationError):
        DescribeCodeQuery(**arguments)


def test_the_result_needs_a_text_and_the_package_info() -> None:
    """Sprawdza, czy wynik bez metryczki paczki albo z pustym opisem kończy się wyjątkiem
    `ValidationError`, a wynik z oboma jest poprawny.

    Wyłapuje wynik z pustym opisem oddany modelowi jak poprawny: wyglądałby jak projekt,
    o którym nie ma nic do powiedzenia."""
    with pytest.raises(ValidationError):
        DescribeCodeResult(package_info=INFO, description="")

    with pytest.raises(ValidationError):
        DescribeCodeResult(description="Aplikacja urzędu.")

    result = DescribeCodeResult(package_info=INFO, description="Aplikacja urzędu.")

    assert result.package_info == INFO
