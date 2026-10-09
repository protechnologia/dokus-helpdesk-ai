"""
Description:
Testy integracyjne narzędzia `find_code_text` na małej paczce w katalogu tymczasowym i na
prawdziwym programie ripgrep: to, czego zestaw syntetyczny nie pokazuje — przycinanie długiej
linii, kształt ścieżki po zawężeniu i odróżnienie błędu modelu od błędu wdrożenia.

| sytuacja                                   | oczekiwanie                                |
|--------------------------------------------|--------------------------------------------|
| linia dłuższa niż limit treści             | ucięta, ze znakiem ucięcia, bez wcięcia    |
| zawężenie zapisane przez `..`              | ścieżki w wyniku w jednej postaci          |
| ścieżka zawężenia spoza paczki             | `UnknownCodePathError`, wraca do modelu    |
| paczki albo ripgrepa nie ma                | błąd konfiguracji, do modelu nie wraca     |
"""

from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.find_code_text import (
    MAX_TEXT_CHARS,
    FindCodeTextQuery,
    FindCodeTextTool,
    UnknownCodePathError,
)
from app.agent_tools.code.find_code_text.base import CUT_MARK
from app.core_service.loader_code_package import CodePackage, CodePackageConfigError
from app.engine_process import ProcessConfigError
from app.engine_process.ripgrep import RipgrepClient
from app.engine_process.ripgrep import client as ripgrep_client

GENERATOR = "src/lib/Numeracja/GeneratorNumeru.php"
LONG_LINE = "        $komunikat = 'Brak sekwencji numeracji" + " i jeszcze" * 30 + "';"
CODE      = [
    "<?php",
    "class GeneratorNumeru",
    "{",
    LONG_LINE,
    "}",
]


def _tool(
    tmp_path: Path,  # katalog tymczasowy testu
) -> FindCodeTextTool:
    """
    Description:
    Buduje narzędzie na paczce z jednym plikiem PHP, w którym czwarta linia jest dłuższa niż
    limit treści w wyniku.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")

    Example result:
        FindCodeTextTool szukające w <tmp_path>/paczka/repo
    """
    file = tmp_path / "paczka" / "repo" / GENERATOR

    file.parent.mkdir(parents=True)
    file.write_text("\n".join(CODE) + "\n", encoding="utf-8")

    return FindCodeTextTool(
        package = CodePackage(tmp_path / "paczka"),
        ripgrep = RipgrepClient(timeout=10.0),
    )


async def test_a_long_line_is_shown_cut_and_without_indentation(tmp_path: Path) -> None:
    """Sprawdza, czy trafiona linia dłuższa niż limit treści wraca bez wcięcia, ucięta do limitu
    i zakończona znakiem ucięcia.

    Wyłapuje narzędzie, które oddaje linie w całości: jedna linia sklejonego kodu potrafi mieć
    tysiące znaków, a wynik ma ich dwadzieścia."""
    result = await _tool(tmp_path).find(FindCodeTextQuery(exact="Brak sekwencji numeracji"))

    [line] = result.lines

    assert len(LONG_LINE.strip()) > MAX_TEXT_CHARS
    assert line.text              == LONG_LINE.strip()[:MAX_TEXT_CHARS] + CUT_MARK
    assert (line.path, line.line) == (GENERATOR, 4)


async def test_a_narrowing_written_with_dots_gives_paths_in_one_form(tmp_path: Path) -> None:
    """Sprawdza, czy zawężenie zapisane przez `..` działa jak zapisane wprost i czy ścieżka
    w wyniku jest w jednej postaci, bez `..`.

    Wyłapuje ścieżkę oddawaną tak, jak model zapisał zawężenie: ten sam plik miałby w dwóch
    szukaniach dwa zapisy, a cytowanie po jednym z nich dawałoby drugie źródło."""
    query = FindCodeTextQuery(exact="class GeneratorNumeru", path="src/lib/Sesja/../Numeracja")

    result = await _tool(tmp_path).find(query)

    assert [line.path for line in result.lines] == [GENERATOR]


@pytest.mark.parametrize(
    "path",
    ["../..", "/etc", "src/brak"],
    ids=["w górę", "bezwzględna", "nie istnieje"],
)
async def test_a_narrowing_that_is_not_in_the_package_is_an_error(
    tmp_path: Path,
    path:     str,
) -> None:
    """Sprawdza, czy zawężenie do ścieżki spoza paczki albo takiej, której nie ma, kończy się
    wyjątkiem `UnknownCodePathError`, który jest odmianą `ToolCallError` i niesie ścieżkę
    w komunikacie.

    Wyłapuje szukanie poza paczką, czyli w plikach kontenera, do których model nie ma mieć
    dostępu, oraz odmowę zgłoszoną innym błędem: nie wróciłaby do modelu jako podpowiedź, tylko
    przerwała całe żądanie."""
    with pytest.raises(UnknownCodePathError) as caught:
        await _tool(tmp_path).find(FindCodeTextQuery(exact="Brak sekwencji", path=path))

    assert isinstance(caught.value, ToolCallError)
    assert path in str(caught.value)


async def test_a_missing_package_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy szukanie na paczce, której nie ma na dysku, kończy się wyjątkiem
    `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak paczki oddawany modelowi jako pusty wynik: instancja bez paczki kodu
    odpowiadałaby „nic nie znaleziono" na każde szukanie, a błąd wdrożenia zostałby
    niezauważony."""
    tool = FindCodeTextTool(
        package = CodePackage(tmp_path / "nie-ma"),
        ripgrep = RipgrepClient(timeout=10.0),
    )

    with pytest.raises(CodePackageConfigError) as caught:
        await tool.find(FindCodeTextQuery(exact="Brak sekwencji"))

    assert not isinstance(caught.value, ToolCallError)


async def test_a_missing_ripgrep_stops_the_call_instead_of_answering_the_model(
    tmp_path:    Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy szukanie przy braku programu ripgrep kończy się wyjątkiem
    `ProcessConfigError`, który nie jest odmianą `ToolCallError`. Test podmienia nazwę programu
    na taką, której nie ma.

    Wyłapuje brak programu oddawany modelowi jako błąd do poprawienia albo jako pusty wynik:
    obraz zbudowany bez ripgrepa wyglądałby wtedy na działający."""
    monkeypatch.setattr(ripgrep_client, "RIPGREP", "nie-ma-takiego-rg")

    with pytest.raises(ProcessConfigError) as caught:
        await _tool(tmp_path).find(FindCodeTextQuery(exact="Brak sekwencji"))

    assert not isinstance(caught.value, ToolCallError)
