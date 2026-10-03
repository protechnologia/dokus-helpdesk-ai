from app.tools.docs.fake_docs import default_sections
from app.tools.docs.list_docs import FakeListDocsTool, ListDocsArgs


async def test_the_listing_has_a_row_for_every_section() -> None:
    """Spis treści → wiersz na każdą sekcję, w kolejności dokumentów, z identyfikatorem do odczytu
    i z liczbą sekcji i dokumentów w nagłówku."""
    tool = FakeListDocsTool()

    text = await tool.run(ListDocsArgs())
    rows = text.split("\n\n", 1)[1].splitlines()

    assert text.startswith("Dokumentacja: sekcji 4, dokumentów 2")
    assert [row.split("]")[0].lstrip("[") for row in rows] == [
        section.section_id for section in default_sections()
    ]


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


async def test_an_empty_documentation_is_just_the_header() -> None:
    """Pusta dokumentacja → sam nagłówek z zerami, bez pustej listy wierszy."""
    text = await FakeListDocsTool(sections=[]).run(ListDocsArgs())

    assert text == "Dokumentacja: sekcji 0, dokumentów 0"


def test_the_listing_cannot_be_cited() -> None:
    """Spis treści → brak `cite()`: źródłem jest dopiero odczytana sekcja."""
    assert not hasattr(FakeListDocsTool(), "cite")
