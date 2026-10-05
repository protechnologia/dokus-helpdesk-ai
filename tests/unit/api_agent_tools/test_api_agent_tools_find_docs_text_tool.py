import json

from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.find_docs_text import FindDocsTextQuery, FindDocsTextTool
from app.db_postgres import DocRow, DocsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `DocsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedziami. Że Postgres naprawdę tak
# dopasowuje, sprawdzają testy na stacku.

SECTIONS = default_sections()
TEXTS    = default_texts()
ROWS     = [
    DocRow.from_section(section, body=TEXTS[section.section_id], ordinal=n).model_dump()
    for n, section in enumerate(SECTIONS)
]

EDORECZENIA, EPUAP, W_TOKU, BRAK_SERWERA = (section.section_id for section in SECTIONS)


def _client(
    substring: dict[str, list[str]] | None = None,  # np. {"PDP-203": ["adm-kancelaria-epuap"]}
    words:     dict[str, list[str]] | None = None,  # np. {"uprawnienie": ["adm-…", "adm-…"]}
) -> ScriptedPostgres:
    """
    Description:
    Klient bez bazy ze zmyśloną dokumentacją: na frazę i na słowa oddaje ustalone identyfikatory.

    Example args:
        substring={"PDP-203": ["adm-kancelaria-epuap"]}
        words={"uprawnienie": ["adm-kancelaria-edoreczenia"]}

    Example result:
        ScriptedPostgres odpowiadający jedną sekcją na frazę „PDP-203"
    """
    return ScriptedPostgres(key="section_id", rows=ROWS, substring=substring, words=words)


def _tool(
    client: ScriptedPostgres,  # np. _client(words={"uprawnienie": [EDORECZENIA]})
    limit:  int = 5,           # np. 5 — RAG_TOP_K
) -> FindDocsTextTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=_client(words={"uprawnienie": ["adm-kancelaria-edoreczenia"]})

    Example result:
        FindDocsTextTool odpowiadające bez bazy
    """
    return FindDocsTextTool(docs=DocsTable(client), limit=limit)


async def test_the_phrase_goes_by_substring_and_the_words_by_dictionary() -> None:
    """Fraza i słowa → jedno zapytanie o podciąg i jedno przez słownik, każde ze swoją wartością:
    fraza ma być szukana dosłownie, a słowa w dowolnej odmianie."""
    client = _client()

    await _tool(client).find(FindDocsTextQuery(exact="Przekaż bufor", words="sekwencja numeracja"))

    assert client.calls == [
        ("substring", "Przekaż bufor"),
        ("words",     "sekwencja numeracja"),
    ]


async def test_a_field_that_was_not_given_is_not_searched() -> None:
    """Samo `exact` → żadnego zapytania przez słownik; samo `words` → żadnego podciągu."""
    only_exact = _client()
    only_words = _client()

    await _tool(only_exact).find(FindDocsTextQuery(exact="PDP-203"))
    await _tool(only_words).find(FindDocsTextQuery(words="uprawnienie"))

    assert [kind for kind, _ in only_exact.calls] == ["substring"]
    assert [kind for kind, _ in only_words.calls] == ["words"]


async def test_either_field_is_enough_for_a_section_to_come_back() -> None:
    """Fraza trafia w jedną sekcję, słowa w inną → obie w wyniku, znaleziona frazą pierwsza:
    pola szukają niezależnie, a wyniki się sumują."""
    client = _client(substring={"PDP-203": [BRAK_SERWERA]}, words={"numeracja": [W_TOKU]})

    result = await _tool(client).find(FindDocsTextQuery(exact="PDP-203", words="numeracja"))

    assert [(found.section.section_id, found.matched_by) for found in result.sections] == [
        (BRAK_SERWERA, "exact"),
        (W_TOKU,       "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_section_found_both_ways_comes_back_once_as_exact() -> None:
    """Fraza i słowa trafiają w tę samą sekcję → sekcja w wyniku raz, z etykietą `exact`,
    i liczona raz."""
    client = _client(substring={"PDP-203": [EPUAP]}, words={"skrzynka": [EPUAP, W_TOKU]})

    result = await _tool(client).find(FindDocsTextQuery(exact="PDP-203", words="skrzynka"))

    assert [(found.section.section_id, found.matched_by) for found in result.sections] == [
        (EPUAP,  "exact"),
        (W_TOKU, "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_matches_over_the_limit_are_counted_and_not_read() -> None:
    """Cztery pasujące sekcje, limit 2 → dwie pierwsze w wyniku, dwie policzone jako pominięte,
    a z tabeli czytane są tylko te dwie: „pokazano dwie z czterech" mówi agentowi, że zapytanie
    było zbyt ogólne."""
    client = _client(words={"uprawnienie": [EDORECZENIA, EPUAP, W_TOKU, BRAK_SERWERA]})

    result = await _tool(client, limit=2).find(FindDocsTextQuery(words="uprawnienie"))

    assert [found.section.section_id for found in result.sections] == [EDORECZENIA, EPUAP]
    assert result.omitted_over_limit == 2
    assert client.calls[-1]          == ("read", [EDORECZENIA, EPUAP])


async def test_the_model_gets_descriptions_and_no_content() -> None:
    """Znaleziona sekcja → opis z metryczki pod identyfikatorem do odczytu, bez treści: tę daje
    `read_docs` i tylko on cytuje."""
    client = _client(substring={"Nie udało się": [BRAK_SERWERA]})
    tool   = _tool(client)

    result = await tool.find(FindDocsTextQuery(exact="Nie udało się"))
    text   = await tool.run(FindDocsTextQuery(exact="Nie udało się"))

    assert result.sections[0].section == SECTIONS[3]
    assert json.loads(text)["sections"][0]["section"]["section_id"] == BRAK_SERWERA
    assert "limity zasobów" not in text


async def test_nothing_found_is_an_empty_result_and_no_read() -> None:
    """Żadna sekcja nie pasuje → pusty wynik bez pominiętych i bez odczytu z tabeli:
    „dokumentacja o tym milczy" to poprawna odpowiedź."""
    client = _client()

    result = await _tool(client).find(FindDocsTextQuery(exact="KSeF", words="faktura"))

    assert result.sections           == []
    assert result.omitted_over_limit == 0
    assert "read" not in [kind for kind, _ in client.calls]


async def test_aclose_closes_the_database_client() -> None:
    """`aclose()` → zamknięty klient Postgresa: sprzątający nie musi wiedzieć, z czego narzędzie
    jest zbudowane."""
    client = _client()

    await _tool(client).aclose()

    assert client.closed
