from app.agent_tools.code.read_code_file import (
    MAX_LINES_PER_READ,
    CodeFileInfo,
    CodeLine,
    FakeReadCodeFileTool,
    ReadCodeFileResult,
    RequestedLines,
    ReturnedLines,
)

# Opis `read_code_file` dla modelu podaje dwie rzeczy, które kod trzyma gdzie indziej: limit
# linii na wywołanie i pola wyniku. Układ opisu sprawdza test kontraktu narzędzi; tu pilnujemy
# tylko tego, żeby opis i kod mówiły to samo.

DESCRIPTION = FakeReadCodeFileTool().description

# Pola wyniku pod pełną ścieżką, tak jak stoją w tabelce „Co zwraca". Nazwy pól zagnieżdżonych
# pochodzą z modeli, więc pole dopisane w modelu trafia tu samo.
RESULT_FIELDS = [
    "path",
    *[f"file_info.{name}" for name in CodeFileInfo.model_fields],
    *[f"requested.{name}" for name in RequestedLines.model_fields],
    *[f"returned.{name}" for name in ReturnedLines.model_fields],
    *[f"lines[].{name}" for name in CodeLine.model_fields],
]


def test_the_description_names_the_line_limit_of_the_code() -> None:
    """Sprawdza, czy opis narzędzia podaje modelowi limit linii na wywołanie równy stałej
    `MAX_LINES_PER_READ`, w zdaniu „najwyżej … linii".

    Wyłapuje zmianę limitu w kodzie bez zmiany opisu: model planowałby odczyty pod inną liczbę
    linii, niż dostaje, i dowiadywał się o tym dopiero z urwanego wyniku."""
    assert f"najwyżej {MAX_LINES_PER_READ} linii" in DESCRIPTION


def test_the_description_explains_every_field_of_the_result() -> None:
    """Sprawdza, czy tabelka wyniku w opisie narzędzia wymienia każde pole, które model dostaje,
    pod pełną ścieżką (na przykład `returned.cut_by_limit`), i czy wynik nie ma części górnego
    poziomu, o której ten test nie wie.

    Wyłapuje pole dopisane w modelu wyniku bez słowa w opisie: model widziałby je w odpowiedzi,
    ale nie wiedziałby, co znaczy — a od flag zakresu zależy, czy ma czytać dalej."""
    returns = DESCRIPTION.split("# Co zwraca")[1].split("# Zasady")[0]

    assert set(ReadCodeFileResult.model_fields) == {
        "path", "file_info", "requested", "returned", "lines",
    }

    for field in RESULT_FIELDS:
        assert f"| {field} " in returns, field
