import json

import pytest

from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH, default_files
from app.agent_tools.code.find_code_text import default_matched
from app.agent_tools.code.quote_code import FakeQuoteCodeTool, QuoteCodeQuery
from app.agent_tools.code.read_code_file import (
    FakeReadCodeFileTool,
    NoSuchCodeFileError,
    ReadCodeFileQuery,
    StartOutOfFileError,
)
from app.core_service.loader_code_package import split_lines

CONDITION = ReadCodeFileQuery(path=GENERATOR_PATH, from_line=7, to_line=9)


async def test_the_fake_returns_the_lines_that_were_asked_for() -> None:
    """Sprawdza, czy atrapa oddaje te linie, o które pytano: trzy linie wbudowanego pliku PHP ze
    swoimi numerami i treścią z pliku, a dla drugiego zapytania cały wbudowany plik JS.

    Wyłapuje atrapę, która na każdy odczyt odpowiada tym samym: test grafu nie odróżniłby wtedy
    jednego pliku od drugiego ani fragmentu od całości."""
    tool  = FakeReadCodeFileTool()
    files = default_files()

    fragment = await tool.read(CONDITION)
    whole    = await tool.read(ReadCodeFileQuery(path=ERRORS_PATH))

    assert [(line.line, line.text) for line in fragment.lines] == list(
        enumerate(split_lines(files[GENERATOR_PATH])[6:9], start=7),
    )
    assert [line.text for line in whole.lines] == split_lines(files[ERRORS_PATH])
    assert (fragment.path, whole.path)         == (GENERATOR_PATH, ERRORS_PATH)


async def test_the_model_reads_the_result_as_json_with_both_ranges() -> None:
    """Sprawdza, czy tekst, który model dostaje od atrapy, to JSON z pięcioma częściami: ścieżką,
    długością pliku, zakresem żądanym, zakresem oddanym z dwiema flagami i liniami z numerem
    i treścią.

    Wyłapuje atrapę z własnym kształtem tekstu dla modelu: test grafu na atrapie sprawdzałby
    wtedy inny tekst niż ten, który model czyta na produkcji."""
    body = json.loads(await FakeReadCodeFileTool().run(CONDITION))

    assert set(body)             == {"path", "file_info", "requested", "returned", "lines"}
    assert body["file_info"]     == {"total_lines": 14}
    assert body["requested"]     == {"from_line": 7, "to_line": 9}
    assert body["returned"]      == {
        "from_line": 7, "to_line": 9, "cut_by_limit": False, "end_of_file": False,
    }
    assert set(body["lines"][0]) == {"line", "text"}
    assert "if (!$sekwencja) {" in body["lines"][1]["text"]


async def test_an_unknown_path_is_an_error() -> None:
    """Sprawdza, czy odczyt pliku, którego atrapa nie zna, kończy się wyjątkiem
    `NoSuchCodeFileError` ze ścieżką w komunikacie.

    Wyłapuje atrapę, która oddaje coś dla dowolnej ścieżki: test grafu nie zobaczyłby wtedy, co
    model dostaje po próbie przeczytania pliku, którego nie ma."""
    with pytest.raises(NoSuchCodeFileError) as caught:
        await FakeReadCodeFileTool().read(ReadCodeFileQuery(path="src/lib/Brak.php"))

    assert "src/lib/Brak.php" in str(caught.value)


async def test_a_start_past_the_end_of_a_known_file_is_an_error() -> None:
    """Sprawdza, czy odczyt od linii za końcem znanego pliku (wbudowany plik PHP ma 14 linii)
    kończy się wyjątkiem `StartOutOfFileError`, a odczyt od ostatniej linii przechodzi.

    Wyłapuje atrapę liczącą linie inaczej niż czytnik paczki: te same numery znaczyłyby co innego
    w teście na atrapie i na prawdziwej paczce."""
    tool = FakeReadCodeFileTool()

    with pytest.raises(StartOutOfFileError) as caught:
        await tool.read(ReadCodeFileQuery(path=GENERATOR_PATH, from_line=15))

    last = await tool.read(ReadCodeFileQuery(path=GENERATOR_PATH, from_line=14))

    assert caught.value.line_count == 14
    assert [line.line for line in last.lines] == [14]


async def test_a_fake_built_without_files_knows_none() -> None:
    """Sprawdza, czy atrapa zbudowana z pustym zestawem plików nie zna także plików wbudowanych:
    odczyt wbudowanego pliku PHP kończy się wyjątkiem `NoSuchCodeFileError`.

    Wyłapuje atrapę, która pusty zestaw bierze za „nie podano": nie dałoby się wtedy odtworzyć
    sprawy, w której w kodzie nie ma niczego do przeczytania."""
    with pytest.raises(NoSuchCodeFileError):
        await FakeReadCodeFileTool(files={}).read(CONDITION)


async def test_every_query_is_recorded_even_a_refused_one() -> None:
    """Sprawdza, czy atrapa zapisuje na liście `queries` każde zapytanie, także to, na które
    odpowiedziała błędem.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie miałby jak sprawdzić, które pliki
    i zakresy agent próbował przeczytać."""
    tool    = FakeReadCodeFileTool()
    unknown = ReadCodeFileQuery(path="src/lib/Brak.php")

    await tool.read(CONDITION)

    with pytest.raises(NoSuchCodeFileError):
        await tool.read(unknown)

    assert tool.queries == [CONDITION, unknown]


async def test_the_three_code_fakes_agree_on_paths_and_lines() -> None:
    """Sprawdza, czy atrapy trzech narzędzi kodu mówią o tych samych plikach tymi samymi
    numerami: każdą linię z wbudowanego wyniku szukania atrapa odczytu oddaje pod tą samą ścieżką
    i numerem, z tą samą treścią bez wcięcia, a atrapa cytowania przyjmuje cytowanie tej linii.

    Wyłapuje atrapy rozjechane między sobą: model w teście grafu czytałby linię znalezioną przez
    szukanie i dostawał inny kod albo błąd, choć na produkcji wszystkie trzy narzędzia czytają
    tę samą paczkę."""
    read  = FakeReadCodeFileTool()
    quote = FakeQuoteCodeTool()

    for found in default_matched():
        query  = ReadCodeFileQuery(path=found.path, from_line=found.line, to_line=found.line)
        [line] = (await read.read(query)).lines

        assert (line.line, line.text.strip()) == (found.line, found.text)

        await quote.search(
            QuoteCodeQuery(path=found.path, from_line=line.line, to_line=line.line, role="cause"),
        )
