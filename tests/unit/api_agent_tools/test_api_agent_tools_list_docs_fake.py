import json

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.list_docs import FakeListDocsTool, ListDocsArgs


async def test_the_listing_describes_every_section() -> None:
    """Spis treści → JSON z opisem każdej sekcji, w kolejności dokumentów, z identyfikatorem do
    odczytu w tym samym polu co w wyszukiwaniach."""
    tool = FakeListDocsTool()
    body = json.loads(await tool.run(ListDocsArgs()))

    assert [section["section_id"] for section in body["sections"]] == [
        section.section_id for section in default_sections()
    ]
    assert body["sections"][0]["chapter_path"] == ["Uprawnienia", "Kancelaria"]


async def test_the_listing_carries_no_content() -> None:
    """Spis treści → opisy sekcji, ale nie ich treść: spis mówi, gdzie co jest, nie co tam stoi."""
    tool = FakeListDocsTool()
    text = await tool.run(ListDocsArgs())

    assert "Kto i gdzie nadaje uprawnienie"  in text
    assert "nadaje administrator w Ustawienia" not in text


async def test_every_call_is_counted() -> None:
    """Każde wywołanie → licznik `calls`, żeby test grafu sprawdził, czy agent sięgnął po spis."""
    tool = FakeListDocsTool()

    await tool.run(ListDocsArgs())
    await tool.run(ListDocsArgs())

    assert tool.calls == 2


async def test_an_empty_documentation_is_an_empty_list() -> None:
    """Pusta dokumentacja → pusta lista sekcji, a nie błąd."""
    body = json.loads(await FakeListDocsTool(sections=[]).run(ListDocsArgs()))

    assert body == {"sections": []}


def test_the_listing_cannot_be_cited() -> None:
    """Spis treści → brak `cite()`: źródłem jest dopiero odczytana sekcja."""
    assert not hasattr(FakeListDocsTool(), "cite")
