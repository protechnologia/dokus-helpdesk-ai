import json

from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH, default_files
from app.agent_tools.code.find_code_text import (
    FakeFindCodeTextTool,
    FindCodeTextQuery,
    MatchedLine,
    default_matched,
)
from app.agent_tools.code.quote_code import FakeQuoteCodeTool, QuoteCodeQuery
from app.core_service.loader_code_package import split_lines

PHRASE = FindCodeTextQuery(exact="Brak sekwencji numeracji")
WORDS  = FindCodeTextQuery(words="skomunikować serwerem", path="src/web/js")


async def test_the_fake_returns_the_same_lines_for_any_query() -> None:
    """Sprawdza, czy atrapa na dwa różne zapytania oddaje ten sam wynik: dwie wbudowane linie,
    pierwszą znalezioną frazą, drugą słowami.

    Wyłapuje atrapę, której wynik zależy od zapytania: test grafu przestałby wiedzieć, co model
    dostał z szukania, a ma to wiedzieć z góry."""
    tool = FakeFindCodeTextTool()

    first  = await tool.find(PHRASE)
    second = await tool.find(WORDS)

    assert first == second
    assert [(line.path, line.matched_by) for line in first.lines] == [
        (GENERATOR_PATH, "exact"),
        (ERRORS_PATH,    "words"),
    ]


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje na liście `queries` każde zapytanie, w kolejności wywołań.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie miałby jak sprawdzić, czego
    i gdzie agent szukał w kodzie."""
    tool = FakeFindCodeTextTool()

    await tool.find(PHRASE)
    await tool.find(WORDS)

    assert tool.queries == [PHRASE, WORDS]


async def test_the_built_in_lines_exist_in_the_fake_files() -> None:
    """Sprawdza, czy każda wbudowana linia atrapy wskazuje prawdziwą linię zmyślonego pliku:
    treść zgadza się z plikiem, a atrapa narzędzia cytującego przyjmuje cytowanie tej linii.

    Wyłapuje wynik szukania rozjechany z plikami atrap: model w teście grafu cytowałby linię
    znalezioną przez szukanie, a atrapa cytowania odpowiadałaby, że takiej linii nie ma."""
    files = default_files()
    quote = FakeQuoteCodeTool()

    for line in default_matched():
        in_file = split_lines(files[line.path])[line.line - 1]

        assert line.text == in_file.strip()

        await quote.search(
            QuoteCodeQuery(path=line.path, from_line=line.line, to_line=line.line, role="cause"),
        )


async def test_own_lines_and_the_omitted_counter_replace_the_built_in_result() -> None:
    """Sprawdza, czy atrapa zbudowana z własnymi liniami i licznikiem pominiętych oddaje właśnie
    je, a zbudowana z pustą listą oddaje pusty wynik, nie zestaw wbudowany.

    Wyłapuje atrapę, która pustą listę bierze za „nie podano": nie dałoby się wtedy odtworzyć
    sprawy, w której tekstu nie ma w kodzie, a to jej najważniejszy scenariusz."""
    own = MatchedLine(path="src/a.php", line=3, matched_by="exact", text="trafienie();")

    general = await FakeFindCodeTextTool(lines=[own], omitted_over_limit=493).find(PHRASE)
    nothing = await FakeFindCodeTextTool(lines=[]).find(PHRASE)

    assert (general.lines, general.omitted_over_limit) == ([own], 493)
    assert (nothing.lines, nothing.omitted_over_limit) == ([], 0)


async def test_the_model_reads_the_result_as_json_with_the_line_text() -> None:
    """Sprawdza, czy tekst, który model dostaje od atrapy, to JSON z listą linii i licznikiem
    pominiętych, a każda linia ma ścieżkę, numer, etykietę i treść.

    Wyłapuje atrapę z własnym kształtem tekstu dla modelu: test grafu na atrapie sprawdzałby
    wtedy inny tekst niż ten, który model czyta na produkcji."""
    body = json.loads(await FakeFindCodeTextTool().run(PHRASE))

    assert set(body)             == {"lines", "omitted_over_limit"}
    assert set(body["lines"][0]) == {"path", "line", "matched_by", "text"}
    assert "Brak sekwencji numeracji" in body["lines"][0]["text"]
