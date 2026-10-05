import json
from datetime import date

import pytest

from app.agent_tools.docs.read_docs import FakeReadDocsTool, ReadDocsQuery, UnknownSectionError

QUERY = ReadDocsQuery(section_ids=["usr-wysylka-status-w-toku", "adm-kancelaria-edoreczenia"])


async def test_sections_come_back_in_the_order_asked() -> None:
    """Sprawdza, czy atrapa odczytu oddaje sekcje w kolejności, w jakiej o nie poproszono, każdą ze
    swoją treścią: dwa identyfikatory dają dwie sekcje, a pierwsza niesie zdanie ze swojej treści.

    Wyłapuje atrapę, która zmienia kolejność albo przypisuje treść nie tej sekcji: test grafu
    dostawałby inny materiał, niż agent wskazał."""
    tool = FakeReadDocsTool()

    result = await tool.search(QUERY)

    assert [item.section.section_id for item in result.sections] == QUERY.section_ids
    assert "nieodwracalne doręczenie" in result.sections[0].text


async def test_a_repeated_id_is_read_once() -> None:
    """Sprawdza, czy identyfikator podany dwa razy daje w wyniku sekcję raz.

    Wyłapuje atrapę, która zachowuje się inaczej niż narzędzie właściwe: baza oddaje wiersz raz,
    więc atrapa oddająca go dwa razy pokazywałaby w testach wynik, którego na produkcji nie ma."""
    query = ReadDocsQuery(section_ids=["adm-kancelaria-epuap", "adm-kancelaria-epuap"])

    result = await FakeReadDocsTool().search(query)

    assert [item.section.section_id for item in result.sections] == ["adm-kancelaria-epuap"]


async def test_an_unknown_id_fails_the_whole_read() -> None:
    """Sprawdza, czy jeden nieznany identyfikator wśród znanych kończy cały odczyt wyjątkiem
    `UnknownSectionError`, który podaje ten identyfikator w polu `section_ids` i w komunikacie.

    Wyłapuje wynik częściowy: odczyt jednej sekcji zamiast dwóch wyglądałby jak poprawny i nikt by
    nie zauważył, że agent pomylił identyfikator."""
    tool  = FakeReadDocsTool()
    query = ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia", "adm-kancelaria-edoreczenie"])

    with pytest.raises(UnknownSectionError) as caught:
        await tool.search(query)

    assert caught.value.section_ids == ["adm-kancelaria-edoreczenie"]
    assert "adm-kancelaria-edoreczenie" in str(caught.value)


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje każde zapytanie w publicznej liście `queries`: po jednym
    odczycie jest tam dokładnie to zapytanie.

    Wyłapuje atrapę, która gubi zapytania: test grafu nie mógłby wtedy sprawdzić, które sekcje agent
    przeczytał."""
    tool = FakeReadDocsTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_the_content_with_its_release() -> None:
    """Sprawdza, czy tekst dla modelu jest JSON-em, w którym każda odczytana sekcja ma
    identyfikator, nazwę dokumentu, wersję, datę wydania i treść.

    Wyłapuje odczyt, który gubi wydanie dokumentu: instrukcji do nieznanego wydania model nie
    odróżni od nieaktualnej."""
    tool = FakeReadDocsTool()
    body = json.loads(tool.render_for_model(await tool.search(QUERY)))

    first = body["sections"][0]

    assert first["section"]["section_id"] == "usr-wysylka-status-w-toku"
    assert first["section"]["document"]   == "Instrukcja użytkownika"
    assert first["section"]["version"]    == "4.12"
    assert [item["section"]["date"] for item in body["sections"]] == ["2026-05-04", "2026-05-04"]
    assert "ponowna wysyłka utworzy drugie, nieodwracalne doręczenie" in first["text"]


async def test_cite_gives_one_source_per_section_read() -> None:
    """Sprawdza, czy `cite()` daje jedno źródło na każdą odczytaną sekcję: z materiału „docs”,
    z tytułem złożonym z dokumentu, wersji i tytułu sekcji oraz z datą wydania, i czy są to
    dokładnie te sekcje, które model dostał w tekście.

    Wyłapuje listę źródeł, która rozjeżdża się z tym, co model przeczytał: źródło bez przeczytanej
    treści albo przeczytaną treść bez źródła."""
    tool   = FakeReadDocsTool()
    result = await tool.search(QUERY)

    refs = tool.cite(result)
    body = json.loads(tool.render_for_model(result))

    assert [ref.item_id for ref in refs] == QUERY.section_ids
    assert all(ref.source == "docs" for ref in refs)
    assert refs[0].title == "Instrukcja użytkownika 4.12 — Status „W toku” przy wysyłce ePUAP"
    assert refs[0].date  == date(2026, 5, 4)
    assert [ref.item_id for ref in refs] == [
        item["section"]["section_id"] for item in body["sections"]
    ]
