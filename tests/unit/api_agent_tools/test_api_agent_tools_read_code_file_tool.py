from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.read_code_file import (
    NoSuchCodeFileError,
    ReadCodeFileQuery,
    ReadCodeFileTool,
    StartOutOfFileError,
)
from app.core_service.loader_code_package import CodePackage, CodePackageConfigError

# Narzędzie stoi na prawdziwym czytniku paczki, a paczka to kilka linii w katalogu tymczasowym —
# sprawdzamy więc, co narzędzie robi z plikiem i z odmową czytnika. Wybieranie zakresu i flagi
# sprawdza test części wspólnej; samej granicy paczki pilnują testy czytnika, a pełną paczkę
# syntetyczną czyta test integracyjny.

GENERATOR = "src/lib/Numeracja/GeneratorNumeru.php"
EMPTY     = "src/lib/Numeracja/Pusty.php"
CODE      = [
    "<?php",
    "class GeneratorNumeru",
    "{",
    "    if (!$sekwencja) {",
    "        throw new BrakSekwencjiException('Brak sekwencji numeracji dla roku ' . $rok);",
    "    }",
    "}",
]


def _tool(
    tmp_path: Path,  # katalog tymczasowy testu
) -> ReadCodeFileTool:
    """
    Description:
    Buduje narzędzie na paczce z dwoma plikami: plikiem PHP na siedem linii i plikiem pustym.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")

    Example result:
        ReadCodeFileTool czytające z <tmp_path>/paczka/repo
    """
    repo = tmp_path / "paczka" / "repo"

    (repo / GENERATOR).parent.mkdir(parents=True)
    (repo / GENERATOR).write_text("\n".join(CODE) + "\n", encoding="utf-8")
    (repo / EMPTY).write_text("", encoding="utf-8")

    return ReadCodeFileTool(package=CodePackage(tmp_path / "paczka"))


async def test_a_range_of_a_file_comes_back_with_its_line_numbers(tmp_path: Path) -> None:
    """Sprawdza, czy odczyt linii 4–6 pliku z paczki oddaje te trzy linie z numerami i treścią
    z pliku, razem z wcięciem, a ścieżka zapisana przez `..` wraca w postaci bez `..`.

    Wyłapuje odczyt, który numeruje linie od zera albo od początku zakresu, oraz ścieżkę oddawaną
    tak, jak podał ją model: cytowanie po takiej ścieżce dawałoby drugie źródło dla tego samego
    pliku."""
    query = ReadCodeFileQuery(
        path      = "src/lib/Sesja/../Numeracja/GeneratorNumeru.php",
        from_line = 4,
        to_line   = 6,
    )

    result = await _tool(tmp_path).read(query)

    assert result.path == GENERATOR
    assert [(line.line, line.text) for line in result.lines] == [
        (4, CODE[3]), (5, CODE[4]), (6, CODE[5]),
    ]


async def test_a_file_without_a_range_comes_back_whole(tmp_path: Path) -> None:
    """Sprawdza, czy odczyt pliku bez zakresu oddaje wszystkie siedem linii, podaje długość pliku
    i oznacza koniec pliku; znak końca linii na końcu pliku nie daje ósmej, pustej linii.

    Wyłapuje odczyt, który dolicza pustą linię po końcu pliku: model mógłby ją zacytować,
    a narzędzie cytujące odpowiedziałoby, że plik takiej linii nie ma."""
    result = await _tool(tmp_path).read(ReadCodeFileQuery(path=GENERATOR))

    assert [line.text for line in result.lines] == CODE
    assert result.file_info.total_lines         == 7
    assert (result.returned.to_line, result.returned.end_of_file) == (7, True)


@pytest.mark.parametrize(
    "path",
    ["../../haslo.yml", "src/lib/Numeracja", "src/lib/Numeracja/Brak.php"],
    ids=["poza paczką", "katalog", "brak pliku"],
)
async def test_a_path_that_is_not_a_file_of_the_package_is_an_error(
    tmp_path: Path,
    path:     str,
) -> None:
    """Sprawdza, czy odczyt ścieżki spoza paczki, katalogu albo pliku, którego nie ma, kończy się
    wyjątkiem `NoSuchCodeFileError`, który jest odmianą `ToolCallError` i niesie ścieżkę
    w komunikacie.

    Wyłapuje odczyt pliku spoza paczki, czyli plików kontenera, do których model nie ma mieć
    dostępu, oraz odmowę zgłoszoną innym błędem: nie wróciłaby do modelu jako podpowiedź, tylko
    przerwała całe żądanie."""
    with pytest.raises(NoSuchCodeFileError) as caught:
        await _tool(tmp_path).read(ReadCodeFileQuery(path=path))

    assert isinstance(caught.value, ToolCallError)
    assert path in str(caught.value)


async def test_a_start_past_the_end_of_the_file_is_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy odczyt od linii 8 w pliku na 7 linii kończy się wyjątkiem
    `StartOutOfFileError`, który jest odmianą `ToolCallError` i podaje długość pliku.

    Wyłapuje odczyt za końcem pliku oddawany jako pusty wynik: wyglądałby jak przeczytany
    fragment, w którym nic nie ma."""
    with pytest.raises(StartOutOfFileError) as caught:
        await _tool(tmp_path).read(ReadCodeFileQuery(path=GENERATOR, from_line=8))

    assert isinstance(caught.value, ToolCallError)
    assert caught.value.line_count == 7


async def test_an_empty_file_is_an_error_not_an_empty_result(tmp_path: Path) -> None:
    """Sprawdza, czy odczyt pliku, który istnieje w paczce, ale nie ma ani jednej linii, kończy
    się wyjątkiem `StartOutOfFileError` z komunikatem, że plik jest pusty.

    Wyłapuje pusty plik oddawany jak brak pliku albo jako wynik bez linii: model nie wiedziałby,
    czy pomylił ścieżkę, czy w pliku naprawdę nic nie ma."""
    with pytest.raises(StartOutOfFileError) as caught:
        await _tool(tmp_path).read(ReadCodeFileQuery(path=EMPTY))

    assert "pusty" in str(caught.value)


async def test_a_missing_package_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy odczyt na paczce, której nie ma na dysku, kończy się wyjątkiem
    `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak paczki oddawany modelowi jako „nie ma takiego pliku": instancja bez paczki kodu
    odpowiadałaby tak na każdy odczyt, a błąd wdrożenia zostałby niezauważony."""
    tool = ReadCodeFileTool(package=CodePackage(tmp_path / "nie-ma"))

    with pytest.raises(CodePackageConfigError) as caught:
        await tool.read(ReadCodeFileQuery(path=GENERATOR))

    assert not isinstance(caught.value, ToolCallError)
