import pytest

from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH, default_files
from app.agent_tools.code.quote_code import (
    FakeQuoteCodeTool,
    LinesOutOfFileError,
    QuoteCodeQuery,
    UnknownCodeFileError,
)

CAUSE = QuoteCodeQuery(path=GENERATOR_PATH, from_line=8, to_line=10, role="cause")


async def test_the_fake_confirms_what_was_quoted() -> None:
    """Sprawdza, czy atrapa potwierdza ten fragment, o który pytano: ścieżkę, zakres linii i rolę
    z zapytania, osobno dla przyczyny i dla miejsca wykluczonego.

    Wyłapuje atrapę, która na każde cytowanie odpowiada tym samym: test grafu nie odróżniłby wtedy
    cytowania przyczyny od wykluczenia ani jednego pliku od drugiego."""
    tool     = FakeQuoteCodeTool()
    excluded = QuoteCodeQuery(path=ERRORS_PATH, from_line=7, to_line=7, role="excluded")

    first  = await tool.search(CAUSE)
    second = await tool.search(excluded)

    assert (first.path, first.from_line, first.to_line) == (GENERATOR_PATH, 8, 10)
    assert (first.role, second.role)                    == ("cause", "excluded")
    assert second.path                                  == ERRORS_PATH


async def test_the_fake_cites_like_the_real_tool() -> None:
    """Sprawdza, czy atrapa robi źródło tylko z cytowania przyczyny, z tym samym kluczem co
    narzędzie właściwe (materiał „code", ścieżka i zakres linii), a z wykluczenia nie robi żadnego.

    Wyłapuje atrapę z własną regułą cytowania: test grafu na atrapie sprawdzałby wtedy inną listę
    źródeł niż ta, która powstaje na produkcji."""
    tool     = FakeQuoteCodeTool()
    cause    = await tool.search(CAUSE)
    excluded = await tool.search(
        QuoteCodeQuery(path=ERRORS_PATH, from_line=7, to_line=7, role="excluded"),
    )

    assert [ref.key for ref in tool.cite(cause)] == [f"code:{GENERATOR_PATH}:8-10"]
    assert tool.cite(excluded)                   == []


async def test_an_unknown_path_is_an_error() -> None:
    """Sprawdza, czy cytowanie pliku, którego atrapa nie zna, kończy się wyjątkiem
    `UnknownCodeFileError` ze ścieżką w komunikacie.

    Wyłapuje atrapę, która potwierdza cytowanie dowolnej ścieżki: test grafu nie zobaczyłby
    wtedy, co model dostaje po cytowaniu pliku, którego nie ma."""
    query = QuoteCodeQuery(path="src/lib/Brak.php", from_line=1, to_line=2, role="cause")

    with pytest.raises(UnknownCodeFileError) as caught:
        await FakeQuoteCodeTool().search(query)

    assert "src/lib/Brak.php" in str(caught.value)


async def test_lines_past_the_end_of_a_known_file_are_an_error() -> None:
    """Sprawdza, czy cytowanie sięgające za ostatnią linię znanego pliku (wbudowany plik PHP ma
    14 linii) kończy się wyjątkiem `LinesOutOfFileError`, a cytowanie ostatniej linii przechodzi.

    Wyłapuje atrapę liczącą linie inaczej niż czytnik paczki: te same numery znaczyłyby co innego
    w teście na atrapie i na prawdziwej paczce."""
    tool      = FakeQuoteCodeTool()
    past_end  = QuoteCodeQuery(path=GENERATOR_PATH, from_line=14, to_line=15, role="cause")
    last_line = QuoteCodeQuery(path=GENERATOR_PATH, from_line=14, to_line=14, role="cause")

    with pytest.raises(LinesOutOfFileError) as caught:
        await tool.search(past_end)

    last = await tool.search(last_line)

    assert caught.value.line_count == 14
    assert last.to_line            == 14


async def test_a_file_ending_with_a_newline_has_no_extra_line() -> None:
    """Sprawdza, czy atrapa zbudowana z własnego pliku zakończonego znakiem nowej linii liczy
    w nim dwie linie, a nie trzy.

    Wyłapuje atrapę, która dolicza pustą linię po końcu pliku: test z własnymi plikami
    przepuszczałby cytowanie linii, której na prawdziwej paczce nie ma."""
    tool = FakeQuoteCodeTool(files={"src/a.php": "<?php\necho 1;\n"})

    with pytest.raises(LinesOutOfFileError):
        await tool.search(QuoteCodeQuery(path="src/a.php", from_line=3, to_line=3, role="cause"))


async def test_every_query_is_recorded_even_a_refused_one() -> None:
    """Sprawdza, czy atrapa zapisuje na liście `queries` każde zapytanie, także to, na które
    odpowiedziała błędem.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie miałby jak sprawdzić, co i w jakiej
    roli agent próbował zacytować."""
    tool    = FakeQuoteCodeTool()
    unknown = QuoteCodeQuery(path="src/lib/Brak.php", from_line=1, to_line=2, role="cause")

    await tool.search(CAUSE)

    with pytest.raises(UnknownCodeFileError):
        await tool.search(unknown)

    assert tool.queries == [CAUSE, unknown]


def test_the_built_in_files_are_the_ones_the_table_names() -> None:
    """Sprawdza, czy wbudowany zestaw plików atrap to dokładnie dwa pliki pod stałymi ścieżkami:
    plik PHP z generatorem numeru i plik JS z obsługą błędów.

    Wyłapuje zmianę ścieżek w zestawie: testy grafów odwołują się do nich wprost, więc zaczęłyby
    cytować pliki, których atrapa nie zna."""
    assert set(default_files()) == {GENERATOR_PATH, ERRORS_PATH}
