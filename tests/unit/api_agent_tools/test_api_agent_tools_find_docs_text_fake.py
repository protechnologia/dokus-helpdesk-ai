import json

from app.agent_tools.docs.find_docs_text import FakeFindDocsTextTool, FindDocsTextQuery

QUERY = FindDocsTextQuery(exact="Nie udało się skomunikować z serwerem")

FOUND_IDS = ["usr-komunikat-brak-serwera", "adm-kancelaria-edoreczenia"]


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same sekcje w tej samej kolejności, dosłowne trafienie pierwsze."""
    tool = FakeFindDocsTextTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [matched.section.section_id for matched in first.sections]  == FOUND_IDS
    assert [matched.section.section_id for matched in second.sections] == FOUND_IDS


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindDocsTextTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_how_each_section_was_found() -> None:
    """Tekst dla modelu → JSON: przy każdej sekcji identyfikator i sposób dopasowania pod nazwą
    pola, którym agent pytał (`exact`, `words`)."""
    tool = FakeFindDocsTextTool()
    body = json.loads(await tool.run(QUERY))

    assert [found["section"]["section_id"] for found in body["sections"]] == FOUND_IDS
    assert [found["matched_by"] for found in body["sections"]]            == ["exact", "words"]


async def test_the_model_gets_no_piece_of_the_content() -> None:
    """Wynik wyszukiwania → opis sekcji bez dopasowanego fragmentu treści: fragment mógłby
    modelowi wystarczyć zamiast odczytu, a wtedy odpowiedź niosłaby treść bez źródła."""
    tool = FakeFindDocsTextTool()
    text = await tool.run(QUERY)
    body = json.loads(text)

    assert set(body["sections"][0]) == {"matched_by", "section"}
    assert "nadaje administrator" not in text


async def test_matches_over_the_limit_are_counted() -> None:
    """Licznik pominiętych ponad limit → w wyniku: mówi agentowi, że zapytanie było za ogólne."""
    tool = FakeFindDocsTextTool(matched=[], omitted_over_limit=12)
    body = json.loads(await tool.run(QUERY))

    assert body == {"sections": [], "omitted_over_limit": 12}


def test_the_search_cannot_be_cited() -> None:
    """Wyszukiwanie w dokumentacji → brak `cite()`: opis sekcji nie jest źródłem."""
    assert not hasattr(FakeFindDocsTextTool(), "cite")
