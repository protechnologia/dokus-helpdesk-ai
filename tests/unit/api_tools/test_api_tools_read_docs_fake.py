from datetime import date

import pytest

from app.tools.read_docs import FakeReadDocsTool, ReadDocsQuery, UnknownSectionError

QUERY = ReadDocsQuery(section_ids=["usr-wysylka-status-w-toku", "adm-kancelaria-edoreczenia"])


async def test_sections_come_back_in_the_order_asked() -> None:
    """Dwa identyfikatory → dwie sekcje w kolejności żądania, każda ze swoją treścią."""
    tool = FakeReadDocsTool()

    result = await tool.search(QUERY)

    assert [item.section.section_id for item in result.items] == QUERY.section_ids
    assert "nieodwracalne doręczenie" in result.items[0].text


async def test_an_unknown_id_fails_the_whole_read() -> None:
    """Jeden nieznany identyfikator wśród znanych → UnknownSectionError z jego nazwą, bez wyniku
    częściowego: odczyt jednej sekcji zamiast dwóch wyglądałby jak poprawny."""
    tool  = FakeReadDocsTool()
    query = ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia", "adm-kancelaria-edoreczenie"])

    with pytest.raises(UnknownSectionError) as caught:
        await tool.search(query)

    assert caught.value.section_ids == ["adm-kancelaria-edoreczenie"]
    assert "adm-kancelaria-edoreczenie" in str(caught.value)


async def test_every_query_is_recorded() -> None:
    """Każdy odczyt → zapytanie w `queries`, żeby test grafu sprawdził, co agent przeczytał."""
    tool = FakeReadDocsTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_the_content_with_its_release() -> None:
    """Tekst dla modelu → przy każdej sekcji identyfikator, dokument z wersją, data wydania
    i treść: instrukcja do nieznanego wydania jest nie do odróżnienia od nieaktualnej."""
    tool = FakeReadDocsTool()

    text = tool.render_for_model(await tool.search(QUERY))

    assert text.startswith("Odczytane sekcje dokumentacji: 2")
    assert "[usr-wysylka-status-w-toku] Instrukcja użytkownika 4.12" in text
    assert text.count("wydanie z 2026-05-04") == 2
    assert "ponowna wysyłka utworzy drugie, nieodwracalne doręczenie" in text


async def test_cite_gives_one_source_per_section_read() -> None:
    """Każda odczytana sekcja → jeden SourceRef z materiału „docs", z dokumentem i tytułem sekcji,
    bez podobieństwa; jego id widać w tekście dla modelu."""
    tool   = FakeReadDocsTool()
    result = await tool.search(QUERY)

    refs = tool.cite(result)
    text = tool.render_for_model(result)

    assert [ref.item_id for ref in refs] == QUERY.section_ids
    assert all(ref.source == "docs" for ref in refs)
    assert all(ref.score is None for ref in refs)
    assert refs[0].title == "Instrukcja użytkownika 4.12 — Status „W toku” przy wysyłce ePUAP"
    assert refs[0].date  == date(2026, 5, 4)
    assert all(f"[{ref.item_id}]" in text for ref in refs)
