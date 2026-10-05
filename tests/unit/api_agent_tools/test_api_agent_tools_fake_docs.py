from app.agent_tools.docs.fake_docs import default_sections, default_texts
from app.agent_tools.docs.find_docs_text import FakeFindDocsTextTool, FindDocsTextQuery
from app.agent_tools.docs.find_docs_vector import FakeFindDocsVectorTool, FindDocsVectorQuery
from app.agent_tools.docs.read_docs import FakeReadDocsTool, ReadDocsQuery


def test_every_section_has_its_content() -> None:
    """Sprawdza, czy zmyślona dokumentacja atrap jest kompletna: każda sekcja ze spisu ma treść
    i nie ma treści bez sekcji.

    Wyłapuje sekcję dopisaną do zestawu bez treści albo treść bez sekcji: atrapa odczytu nie miałaby
    czego oddać dla sekcji, którą pokazuje spis."""
    assert set(default_texts()) == {section.section_id for section in default_sections()}


def test_section_ids_are_unique() -> None:
    """Sprawdza, czy identyfikatory sekcji w zmyślonej dokumentacji się nie powtarzają.

    Wyłapuje dwie sekcje o tym samym identyfikatorze: po nim idzie odczyt i klucz źródła, więc
    jednej z nich nie dałoby się odczytać ani zacytować."""
    ids = [section.section_id for section in default_sections()]

    assert len(ids) == len(set(ids))


async def test_whatever_a_search_fake_finds_the_read_fake_can_read() -> None:
    """Sprawdza, czy każdy identyfikator zwrócony przez atrapy obu wyszukiwań, po znaczeniu
    i tekstowego, da się odczytać atrapą odczytu.

    Wyłapuje atrapy stojące na różnych zestawach sekcji: graf na atrapach nie przeszedłby drogi od
    wyszukania do źródła, bo odczyt znalezionej sekcji kończyłby się błędem."""
    vector = await FakeFindDocsVectorTool().find(FindDocsVectorQuery(text="uprawnienia"))
    text   = await FakeFindDocsTextTool().find(FindDocsTextQuery(words="uprawnienia"))
    found  = sorted({item.section.section_id for item in [*vector.sections, *text.sections]})

    result = await FakeReadDocsTool().search(ReadDocsQuery(section_ids=found))

    assert [item.section.section_id for item in result.sections] == found
