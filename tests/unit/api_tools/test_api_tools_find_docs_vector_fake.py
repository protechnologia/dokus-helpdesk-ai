from app.tools.docs.find_docs_vector import FakeFindDocsVectorTool, FindDocsVectorQuery

QUERY = FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")

FOUND_IDS = ["adm-kancelaria-edoreczenia", "adm-kancelaria-epuap"]


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same sekcje w tej samej kolejności: atrapa ma być przewidywalna."""
    tool = FakeFindDocsVectorTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [found.section.section_id for found in first.items]  == FOUND_IDS
    assert [found.section.section_id for found in second.items] == FOUND_IDS


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindDocsVectorTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_rows_it_can_read_by_id() -> None:
    """Tekst dla modelu → identyfikator każdej sekcji w nawiasie, wydanie i podobieństwo, a treści
    sekcji nie ma: po nią agent idzie do `read_docs`."""
    tool = FakeFindDocsVectorTool()

    text = await tool.run(QUERY)

    assert all(f"[{section_id}]" in text for section_id in FOUND_IDS)
    assert text.count("Instrukcja administratora 4.12") == 2
    assert "podobieństwo 0.74" in text
    assert "nadaje administrator" not in text


async def test_a_cut_threshold_is_told_apart_from_no_hits() -> None:
    """Brak sekcji i licznik odciętych → nagłówek niesie oba: „nic nie było" i „próg wszystko
    wyciął" to dla agenta różne sytuacje."""
    tool = FakeFindDocsVectorTool(found=[], dropped_below_threshold=3)

    text = await tool.run(QUERY)

    assert text == "Znalezione sekcje dokumentacji: 0 (odcięte progiem: 3)"


def test_the_search_cannot_be_cited() -> None:
    """Wyszukiwanie w dokumentacji → brak `cite()`: wiersz spisu treści nie jest źródłem."""
    assert not hasattr(FakeFindDocsVectorTool(), "cite")
