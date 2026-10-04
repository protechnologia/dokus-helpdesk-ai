import json

from app.agent_tools.tickets.find_tickets_vector import (
    FakeFindTicketsVectorTool,
    FindTicketsVectorQuery,
)

QUERY = FindTicketsVectorQuery(
    problem  = "Nie przychodzą przesyłki",
    symptoms = "pusta skrzynka odbiorcza",
)


async def test_the_result_is_the_same_on_every_search() -> None:
    """Dwa wyszukiwania → te same numery w tej samej kolejności: atrapa ma być przewidywalna, żeby
    test grafu nie zależał od tego, którym z kolei wywołaniem jest."""
    tool = FakeFindTicketsVectorTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [found.ticket_id for found in first.tickets]  == ["90001", "90002", "90003"]
    assert [found.ticket_id for found in second.tickets] == ["90001", "90002", "90003"]


async def test_every_query_is_recorded() -> None:
    """Każde wyszukiwanie → zapytanie w `queries`, żeby test grafu sprawdził, o co pytał agent."""
    tool = FakeFindTicketsVectorTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_numbers_and_scores_and_nothing_else() -> None:
    """Tekst dla modelu → JSON z numerem i podobieństwem każdego zgłoszenia, od najbardziej
    podobnego; treści karty nie ma, więc model musi ją odczytać."""
    body = json.loads(await FakeFindTicketsVectorTool().run(QUERY))

    assert body == {
        "tickets": [
            {"ticket_id": "90001", "score": 0.91},
            {"ticket_id": "90002", "score": 0.89},
            {"ticket_id": "90003", "score": 0.86},
        ],
        "dropped_below_threshold": 0,
    }


async def test_an_empty_result_says_what_the_threshold_cut() -> None:
    """Brak zgłoszeń i trzy odcięte → wynik niesie oba: „nic nie było" i „próg to wyciął" to dla
    agenta różne sytuacje."""
    tool = FakeFindTicketsVectorTool(tickets=[], dropped_below_threshold=3)
    body = json.loads(await tool.run(QUERY))

    assert body == {"tickets": [], "dropped_below_threshold": 3}


def test_the_search_cannot_be_cited() -> None:
    """Wyszukiwanie zgłoszeń → brak `cite()`: numer zgłoszenia nie jest źródłem, źródłem jest
    dopiero odczytana karta albo wątek."""
    assert not hasattr(FakeFindTicketsVectorTool(), "cite")
