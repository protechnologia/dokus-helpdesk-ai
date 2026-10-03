from app.tools.find_docs_vector import FakeFindDocsVector, FindDocsVectorQuery

QUERY = FindDocsVectorQuery(text="uprawnienia kancelaria e-Doręczenia")


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same id w tej samej kolejności: atrapa ma być przewidywalna."""
    tool = FakeFindDocsVector()

    first  = await tool.search(QUERY)
    second = await tool.search(QUERY)

    assert [found.fragment_id for found in first.items]  == ["doc-1", "doc-2"]
    assert [found.fragment_id for found in second.items] == ["doc-1", "doc-2"]


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindDocsVector()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_cite_gives_one_source_per_fragment_shown() -> None:
    """Każdy fragment z wyniku → jeden SourceRef z dokumentem i wersją w tytule, a jego id widać
    w tekście dla modelu: cytować wolno tylko to, co model zobaczył."""
    tool   = FakeFindDocsVector()
    result = await tool.search(QUERY)

    refs = tool.cite(result)
    text = tool.render_for_model(result)

    assert [ref.item_id for ref in refs] == ["doc-1", "doc-2"]
    assert all(ref.source == "docs" for ref in refs)
    assert refs[0].title == "Instrukcja administratora 4.12"
    assert all(f"[{ref.item_id}]" in text for ref in refs)


async def test_the_model_sees_the_release_of_each_fragment() -> None:
    """Tekst dla modelu → wersja przy każdym fragmencie: instrukcja do nieznanego wydania jest
    nie do odróżnienia od nieaktualnej."""
    tool = FakeFindDocsVector()

    text = tool.render_for_model(await tool.search(QUERY))

    assert text.count("wersja 4.12") == 2
