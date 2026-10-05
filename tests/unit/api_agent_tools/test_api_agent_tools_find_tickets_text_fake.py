import json

from app.agent_tools.tickets.find_tickets_text import FakeFindTicketsTextTool, FindTicketsTextQuery

QUERY = FindTicketsTextQuery(exact="Nie udało się skomunikować z serwerem")


async def test_the_result_is_the_same_on_every_search() -> None:
    """Sprawdza, czy atrapa wyszukiwania tekstowego oddaje za każdym razem ten sam wynik: dwa
    wyszukiwania dają numery zgłoszeń `90011` i `90012` w tej samej kolejności.

    Wyłapuje atrapę, której wynik zależy od tego, którym z kolei wywołaniem jest wyszukiwanie:
    test grafu oparty na niej przestałby być przewidywalny."""
    tool = FakeFindTicketsTextTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [matched.ticket_id for matched in first.tickets]  == ["90011", "90012"]
    assert [matched.ticket_id for matched in second.tickets] == ["90011", "90012"]


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje zapytanie w publicznej liście `queries`: po jednym
    wyszukiwaniu jest tam dokładnie to zapytanie.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie mógłby wtedy sprawdzić, o co
    agent pytał."""
    tool = FakeFindTicketsTextTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_numbers_and_how_each_was_found() -> None:
    """Sprawdza, czy tekst dla modelu to JSON z numerem każdego zgłoszenia, z tym, czym je
    znaleziono (`exact` albo `words`, czyli nazwa pola, którym agent pytał), i z licznikiem
    pominiętych. Słowa „skomunikować", które jest w szukanym komunikacie, w tym tekście nie ma.

    Wyłapuje wynik wyszukiwania, który niesie wątek albo jego fragment: model mógłby wtedy
    odpowiedzieć bez odczytania wątku, a taka odpowiedź nie ma źródła."""
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
    """Sprawdza, czy liczba zgłoszeń pominiętych ponad limit trafia do tekstu dla modelu: atrapa
    ustawiona na pusty wynik i 35 pominiętych oddaje pustą listę i liczbę 35.

    Wyłapuje wynik, który gubi ten licznik: agent nie dowiedziałby się, że jego zapytanie było
    za ogólne."""
    tool = FakeFindTicketsTextTool(tickets=[], omitted_over_limit=35)
    body = json.loads(await tool.run(QUERY))

    assert body == {"tickets": [], "omitted_over_limit": 35}


def test_the_search_cannot_be_cited() -> None:
    """Sprawdza, czy atrapa wyszukiwania tekstowego nie ma metody `cite()`, którą narzędzia
    odczytu podają źródła odpowiedzi.

    Wyłapuje wyszukiwanie, które zaczęło cytować: sam numer znalezionego zgłoszenia trafiłby
    wtedy na listę źródeł, choć numer zgłoszenia nie jest źródłem."""
    assert not hasattr(FakeFindTicketsTextTool(), "cite")
