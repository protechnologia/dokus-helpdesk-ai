import json

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.list_docs import FakeListDocsTool, ListDocsArgs


async def test_the_listing_describes_every_section() -> None:
    """Sprawdza, czy spis treści z atrapy to JSON z opisem każdej sekcji, w kolejności dokumentów,
    z identyfikatorem w polu `section_id` i ze ścieżką rozdziałów.

    Wyłapuje spis niepełny, w innej kolejności albo z identyfikatorem pod inną nazwą niż
    w wyszukiwaniach: agent nie wiedziałby, co podać narzędziu odczytu."""
    tool = FakeListDocsTool()
    body = json.loads(await tool.run(ListDocsArgs()))

    assert [section["section_id"] for section in body["sections"]] == [
        section.section_id for section in default_sections()
    ]
    assert body["sections"][0]["chapter_path"] == ["Uprawnienia", "Kancelaria"]


async def test_the_listing_carries_no_content() -> None:
    """Sprawdza, czy spis treści niesie opisy sekcji, ale nie ich treść: w tekście dla modelu jest
    opis pierwszej sekcji, a nie ma zdania z jej treści.

    Wyłapuje treść sekcji dołożoną do spisu: spis ma mówić, gdzie co jest, a nie co tam stoi."""
    tool = FakeListDocsTool()
    text = await tool.run(ListDocsArgs())

    assert "Kto i gdzie nadaje uprawnienie"  in text
    assert "nadaje administrator w Ustawienia" not in text


async def test_every_call_is_counted() -> None:
    """Sprawdza, czy atrapa liczy wywołania w publicznym polu `calls`: po dwóch wywołaniach licznik
    wynosi 2.

    Wyłapuje atrapę, która nie liczy wywołań: test grafu nie mógłby sprawdzić, czy agent sięgnął po
    spis treści."""
    tool = FakeListDocsTool()

    await tool.run(ListDocsArgs())
    await tool.run(ListDocsArgs())

    assert tool.calls == 2


async def test_an_empty_documentation_is_an_empty_list() -> None:
    """Sprawdza, czy atrapa zbudowana z pustą listą sekcji oddaje modelowi pustą listę, a nie błąd.

    Wyłapuje atrapę, która przy pustej liście zgłasza błąd albo podstawia wbudowane sekcje: nie
    dałoby się wtedy przetestować grafu na pustej dokumentacji."""
    body = json.loads(await FakeListDocsTool(sections=[]).run(ListDocsArgs()))

    assert body == {"sections": []}


def test_the_listing_cannot_be_cited() -> None:
    """Sprawdza, czy atrapa spisu treści nie ma metody `cite()`.

    Wyłapuje spis, który zaczął cytować: na listę źródeł trafiłyby sekcje, których model nie
    przeczytał, a źródłem jest dopiero odczytana sekcja."""
    assert not hasattr(FakeListDocsTool(), "cite")
