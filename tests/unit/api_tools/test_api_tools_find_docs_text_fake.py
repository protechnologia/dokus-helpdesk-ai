from app.tools.docs.find_docs_text import FakeFindDocsTextTool, FindDocsTextQuery

QUERY = FindDocsTextQuery(exact=["Nie udało się skomunikować z serwerem"])

FOUND_IDS = ["usr-komunikat-brak-serwera", "adm-kancelaria-edoreczenia"]


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same sekcje w tej samej kolejności, dosłowne trafienie pierwsze."""
    tool = FakeFindDocsTextTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [matched.section.section_id for matched in first.items]  == FOUND_IDS
    assert [matched.section.section_id for matched in second.items] == FOUND_IDS


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindDocsTextTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_how_each_section_was_found() -> None:
    """Tekst dla modelu → przy każdej sekcji identyfikator, etykieta dopasowania i fragment, po
    którym agent decyduje o odczycie."""
    tool = FakeFindDocsTextTool()

    text = await tool.run(QUERY)

    assert all(f"[{section_id}]" in text for section_id in FOUND_IDS)
    assert "dopasowanie: dosłowny ciąg" in text
    assert "dopasowanie: słowa"         in text
    assert text.count("fragment: ") == 2


async def test_matches_over_the_limit_are_counted() -> None:
    """Licznik pominiętych ponad limit → w nagłówku: mówi agentowi, że zapytanie było za ogólne."""
    tool = FakeFindDocsTextTool(matched=[], omitted_over_limit=12)

    text = await tool.run(QUERY)

    assert text == "Znalezione sekcje dokumentacji: 0 (pominięte ponad limit: 12)"


def test_the_search_cannot_be_cited() -> None:
    """Wyszukiwanie w dokumentacji → brak `cite()`: wiersz z fragmentem nie jest źródłem."""
    assert not hasattr(FakeFindDocsTextTool(), "cite")
