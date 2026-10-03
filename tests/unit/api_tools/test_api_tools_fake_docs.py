from app.tools.docs.fake_docs import default_sections, default_texts
from app.tools.docs.find_docs_text import FakeFindDocsTextTool, FindDocsTextQuery
from app.tools.docs.find_docs_vector import FakeFindDocsVectorTool, FindDocsVectorQuery
from app.tools.docs.read_docs import FakeReadDocsTool, ReadDocsQuery


def test_every_section_has_its_content() -> None:
    """Zmyślona dokumentacja → treść dla każdej sekcji ze spisu i żadnej treści bez sekcji."""
    assert set(default_texts()) == {section.section_id for section in default_sections()}


def test_section_ids_are_unique() -> None:
    """Identyfikatory sekcji → bez powtórzeń: po nich idzie odczyt i klucz źródła."""
    ids = [section.section_id for section in default_sections()]

    assert len(ids) == len(set(ids))


async def test_whatever_a_search_fake_finds_the_read_fake_can_read() -> None:
    """Identyfikatory z atrap obu wyszukiwań → do odczytania atrapą odczytu, jak na produkcji:
    graf na atrapach może przejść całą drogę od wyszukania do źródła."""
    vector = await FakeFindDocsVectorTool().find(FindDocsVectorQuery(text="uprawnienia"))
    text   = await FakeFindDocsTextTool().find(FindDocsTextQuery(words="uprawnienia"))
    found  = sorted({item.section.section_id for item in [*vector.items, *text.items]})

    result = await FakeReadDocsTool().search(ReadDocsQuery(section_ids=found))

    assert [item.section.section_id for item in result.items] == found
