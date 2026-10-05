import json

from app.agent_tools.tickets.find_tickets_text import FakeFindTicketsTextTool, FindTicketsTextQuery

QUERY = FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem")


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same numery w tej samej kolejności: atrapa ma być przewidywalna."""
    tool = FakeFindTicketsTextTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [matched.ticket_id for matched in first.tickets]  == ["90011", "90012"]
    assert [matched.ticket_id for matched in second.tickets] == ["90011", "90012"]


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindTicketsTextTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_numbers_and_how_each_was_found() -> None:
    """Tekst dla modelu → JSON z numerem i sposobem dopasowania pod nazwą pola, którym agent
    pytał; wątku ani jego fragmentu nie ma, więc model musi je odczytać."""
    text = await FakeFindTicketsTextTool().run(QUERY)
    body = json.loads(text)

    assert body == {
        "tickets": [
            {"ticket_id": "90011", "matched_by": "exact"},
            {"ticket_id": "90012", "matched_by": "words"},
        ],
        "omitted_over_limit": 0,
    }
    assert "skomunikować" not in text


async def test_matches_over_the_limit_are_counted() -> None:
    """Licznik pominiętych ponad limit → w wyniku: mówi agentowi, że zapytanie było za ogólne."""
    tool = FakeFindTicketsTextTool(tickets=[], omitted_over_limit=35)
    body = json.loads(await tool.run(QUERY))

    assert body == {"tickets": [], "omitted_over_limit": 35}


def test_the_search_cannot_be_cited() -> None:
    """Wyszukiwanie zgłoszeń → brak `cite()`: numer zgłoszenia nie jest źródłem."""
    assert not hasattr(FakeFindTicketsTextTool(), "cite")
