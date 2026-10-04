import json
from datetime import date

from app.agent_tools.tickets.read_tickets_card import FakeReadTicketsCardTool, ReadTicketsCardQuery

QUERY = ReadTicketsCardQuery(ticket_ids=["90002", "90011", "90001"])


async def test_cards_come_back_in_the_order_asked() -> None:
    """Trzy numery, jeden bez karty → dwie karty w kolejności żądania i numer bez karty osobno."""
    result = await FakeReadTicketsCardTool().search(QUERY)

    assert [card.ticket_id for card in result.cards] == ["90002", "90001"]
    assert result.without_card                       == ["90011"]


async def test_a_number_asked_twice_is_read_once() -> None:
    """Numer podany dwa razy → jedna karta: model nie ma dostać tego samego rekordu dwukrotnie."""
    query  = ReadTicketsCardQuery(ticket_ids=["90001", "90001", "90011", "90011"])
    result = await FakeReadTicketsCardTool().search(query)

    assert [card.ticket_id for card in result.cards] == ["90001"]
    assert result.without_card                       == ["90011"]


async def test_every_query_is_recorded() -> None:
    """Każdy odczyt → zapytanie w `queries`, żeby test grafu sprawdził, co agent przeczytał."""
    tool = FakeReadTicketsCardTool()

    await tool.search(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_sees_every_card_field_under_its_schema_name() -> None:
    """Tekst dla modelu → JSON z polami karty pod nazwami ze schematu: prompty grafów odwołują
    się do nich po nazwie (`cause`, `solution`, `questions_summary`)."""
    tool = FakeReadTicketsCardTool()
    body = json.loads(tool.render_for_model(await tool.search(QUERY)))

    card = body["cards"][0]

    assert set(card) == {
        "ticket_id",
        "date",
        "component",
        "problem",
        "symptoms",
        "error_codes",
        "cause",
        "solution",
        "resolution",
        "questions_summary",
    }
    assert card["ticket_id"] == "90002"
    assert card["date"]      == "2026-04-22"
    assert card["cause"]     == "Plik blokady pozostawiony po aktualizacji blokował pobieranie"
    assert body["without_card"] == ["90011"]


async def test_the_model_does_not_see_artifact_metadata() -> None:
    """Tekst dla modelu → bez wersji słownika rozstrzygnięć: to metadane artefaktu, nie treść
    zgłoszenia, a model potraktowałby je jak fakt o sprawie."""
    tool = FakeReadTicketsCardTool()
    text = tool.render_for_model(await tool.search(QUERY))

    assert "resolution_vocabulary_version" not in text


async def test_the_three_default_cards_share_a_symptom_and_differ_in_cause() -> None:
    """Zestaw wbudowany → jeden objaw, trzy przyczyny: najczęstszy kształt trafień w korpusie,
    na którym agent ma przeczytać wszystkie karty, zamiast poprzestać na pierwszej."""
    query  = ReadTicketsCardQuery(ticket_ids=["90001", "90002", "90003"])
    result = await FakeReadTicketsCardTool().search(query)

    assert len({card.problem for card in result.cards}) == 1
    assert len({card.cause for card in result.cards})   == 3


async def test_cite_gives_one_source_per_card_read() -> None:
    """Każda odczytana karta → jeden SourceRef z materiału „tickets", z `problem` jako tytułem
    i datą zgłoszenia; numer bez karty źródłem nie jest."""
    tool   = FakeReadTicketsCardTool()
    result = await tool.search(QUERY)

    refs = tool.cite(result)

    assert [ref.item_id for ref in refs] == ["90002", "90001"]
    assert all(ref.source == "tickets" for ref in refs)
    assert refs[0].title == "Nie przychodzą przesyłki z e-Doręczeń"
    assert refs[0].date  == date(2026, 4, 22)


async def test_reading_only_tickets_without_cards_cites_nothing() -> None:
    """Sam numer bez karty → pusty wynik i pusta lista źródeł: `requires_hits` nie przepuści
    wtedy propozycji opartej na niczym."""
    tool   = FakeReadTicketsCardTool()
    result = await tool.search(ReadTicketsCardQuery(ticket_ids=["90011"]))

    assert result.cards      == []
    assert tool.cite(result) == []
