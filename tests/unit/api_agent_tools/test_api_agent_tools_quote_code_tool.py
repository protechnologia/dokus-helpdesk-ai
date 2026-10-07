import json
from pathlib import Path

import pytest

from app.agent_tools import ToolCallError
from app.agent_tools.code.quote_code import (
    LinesOutOfFileError,
    QuoteCodeQuery,
    QuoteCodeTool,
    UnknownCodeFileError,
)
from app.core_service.loader_code_package import CodePackage, CodePackageConfigError

# Narzędzie stoi na prawdziwym czytniku paczki, a paczka to kilka linii w katalogu tymczasowym —
# sprawdzamy więc, co narzędzie robi z plikiem i z odmową czytnika. Samej granicy paczki pilnują
# testy czytnika; pełną paczkę syntetyczną czyta test integracyjny.

GENERATOR = "src/lib/Numeracja/GeneratorNumeru.php"
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
) -> QuoteCodeTool:
    """
    Description:
    Buduje narzędzie na paczce z jednym plikiem PHP na siedem linii.

    Example args:
        tmp_path=Path("/tmp/pytest-of-root/pytest-0/test_x0")

    Example result:
        QuoteCodeTool cytujące z <tmp_path>/paczka/repo
    """
    file = tmp_path / "paczka" / "repo" / GENERATOR

    file.parent.mkdir(parents=True)
    file.write_text("\n".join(CODE) + "\n", encoding="utf-8")

    return QuoteCodeTool(package=CodePackage(tmp_path / "paczka"))


async def test_a_quote_comes_back_as_a_confirmation(tmp_path: Path) -> None:
    """Sprawdza, czy cytowanie istniejącego fragmentu wraca jako potwierdzenie z tą samą rolą
    i tym samym zakresem linii, a ścieżka zapisana przez `..` wraca w postaci bez `..`.

    Wyłapuje potwierdzenie, które gubi rolę albo zakres, oraz ścieżkę oddawaną tak, jak podał ją
    model: ten sam fragment zapisany na dwa sposoby byłby wtedy dwoma źródłami."""
    query = QuoteCodeQuery(
        path      = "src/lib/Sesja/../Numeracja/GeneratorNumeru.php",
        from_line = 4,
        to_line   = 6,
        role      = "cause",
    )

    quote = await _tool(tmp_path).search(query)

    assert (quote.path, quote.from_line, quote.to_line, quote.role) == (GENERATOR, 4, 6, "cause")


async def test_the_model_does_not_get_the_quoted_lines(tmp_path: Path) -> None:
    """Sprawdza, czy tekst, który model dostaje po cytowaniu, to JSON z czterema polami (ścieżka,
    pierwsza i ostatnia linia, rola) i czy nie ma w nim treści cytowanych linii.

    Wyłapuje cytowanie, które oddaje kod: model używałby go wtedy zamiast odczytu i cytował
    linie, których nie przeczytał."""
    tool  = _tool(tmp_path)
    quote = await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=4, to_line=6, role="cause"))

    text = tool.render_for_model(quote)

    assert set(json.loads(text)) == {"path", "from_line", "to_line", "role"}
    assert "sekwencj" not in text


async def test_a_cause_becomes_a_source_with_the_path_and_the_lines(tmp_path: Path) -> None:
    """Sprawdza, czy fragment zacytowany jako przyczyna daje jedno źródło z materiałem „code",
    identyfikatorem ze ścieżki i zakresu linii oraz tytułem ze ścieżki i tego samego zakresu
    słowami; źródło nie ma daty.

    Wyłapuje źródło, po którym człowiek nie trafi do kodu: bez zakresu linii wskazywałoby cały
    plik, a z samą nazwą pliku w tytule nie dałoby się odróżnić kontrolerów o tej samej nazwie."""
    tool  = _tool(tmp_path)
    quote = await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=4, to_line=6, role="cause"))

    [ref] = tool.cite(quote)

    assert ref.key   == f"code:{GENERATOR}:4-6"
    assert ref.title == f"{GENERATOR}, linie 4–6"
    assert ref.date  is None


async def test_a_one_line_cause_is_titled_as_one_line(tmp_path: Path) -> None:
    """Sprawdza, czy źródło z fragmentu o jednej linii ma w tytule „linia 5", a w identyfikatorze
    ten sam numer na obu końcach zakresu.

    Wyłapuje tytuł „linie 5–5", który wygląda na pomyłkę, oraz identyfikator w innym kształcie
    niż przy dłuższym fragmencie: wołający musiałby rozpoznawać dwa zapisy."""
    tool  = _tool(tmp_path)
    quote = await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=5, to_line=5, role="cause"))

    [ref] = tool.cite(quote)

    assert ref.item_id == f"{GENERATOR}:5-5"
    assert ref.title   == f"{GENERATOR}, linia 5"


async def test_an_excluded_place_is_confirmed_but_is_not_a_source(tmp_path: Path) -> None:
    """Sprawdza, czy fragment zacytowany jako wykluczony dostaje potwierdzenie, ale nie daje
    żadnego źródła.

    Wyłapuje cytowanie, które robi źródło z każdej roli: wariant wymagający źródeł oddałby wtedy
    rozwiązanie w sprawie, w której model napisał, że kod za opisane zachowanie nie odpowiada."""
    tool  = _tool(tmp_path)
    quote = await tool.search(
        QuoteCodeQuery(path=GENERATOR, from_line=4, to_line=6, role="excluded"),
    )

    assert quote.role       == "excluded"
    assert tool.cite(quote) == []


@pytest.mark.parametrize(
    "path",
    ["../../haslo.yml", "src/lib/Numeracja", "src/lib/Numeracja/Brak.php"],
    ids=["poza paczką", "katalog", "brak pliku"],
)
async def test_a_path_that_is_not_a_file_of_the_package_is_an_error(
    tmp_path: Path,
    path:     str,
) -> None:
    """Sprawdza, czy cytowanie ścieżki spoza paczki, katalogu albo pliku, którego nie ma, kończy
    się wyjątkiem `UnknownCodeFileError`, który jest odmianą `ToolCallError` i niesie ścieżkę
    w komunikacie.

    Wyłapuje cytowanie pliku, którego nie ma, przyjęte jak poprawne, oraz odmowę zgłoszoną innym
    błędem: nie wróciłaby do modelu jako podpowiedź, tylko przerwała całe żądanie."""
    query = QuoteCodeQuery(path=path, from_line=1, to_line=2, role="cause")

    with pytest.raises(UnknownCodeFileError) as caught:
        await _tool(tmp_path).search(query)

    assert isinstance(caught.value, ToolCallError)
    assert path in str(caught.value)


async def test_lines_past_the_end_of_the_file_are_an_error(tmp_path: Path) -> None:
    """Sprawdza, czy fragment kończący się na linii 8 w pliku na 7 linii kończy się wyjątkiem
    `LinesOutOfFileError` z długością pliku w komunikacie, a fragment kończący się na ostatniej,
    siódmej linii przechodzi.

    Wyłapuje cytowanie przycinane po cichu do końca pliku oraz granicę przesuniętą o jedną linię:
    numery, które nie pasują do pliku, znaczą, że model cytuje z pamięci albo pomylił pliki."""
    tool = _tool(tmp_path)

    with pytest.raises(LinesOutOfFileError) as caught:
        await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=6, to_line=8, role="cause"))

    last = await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=6, to_line=7, role="cause"))

    assert caught.value.line_count == 7
    assert "7" in str(caught.value)
    assert last.to_line == 7


async def test_a_missing_package_stops_the_call_instead_of_answering_the_model(
    tmp_path: Path,
) -> None:
    """Sprawdza, czy cytowanie na paczce, której nie ma na dysku, kończy się wyjątkiem
    `CodePackageConfigError`, który nie jest odmianą `ToolCallError`.

    Wyłapuje brak paczki oddawany modelowi jako „nie ma takiego pliku": instancja bez paczki kodu
    odpowiadałaby tak na każde cytowanie, a błąd wdrożenia zostałby niezauważony."""
    tool = QuoteCodeTool(package=CodePackage(tmp_path / "nie-ma"))

    with pytest.raises(CodePackageConfigError) as caught:
        await tool.search(QuoteCodeQuery(path=GENERATOR, from_line=1, to_line=2, role="cause"))

    assert not isinstance(caught.value, ToolCallError)
