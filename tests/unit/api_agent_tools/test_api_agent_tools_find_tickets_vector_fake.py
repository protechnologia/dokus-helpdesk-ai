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
    """Sprawdza, czy atrapa wyszukiwania po znaczeniu oddaje za każdym razem ten sam wynik: dwa
    wyszukiwania dają numery zgłoszeń `90001`, `90002` i `90003` w tej samej kolejności.

    Wyłapuje atrapę, której wynik zależy od tego, którym z kolei wywołaniem jest wyszukiwanie:
    test grafu oparty na niej przestałby być przewidywalny."""
    tool = FakeFindTicketsVectorTool()

    first  = await tool.find(QUERY)
    second = await tool.find(QUERY)

    assert [found.ticket_id for found in first.tickets]  == ["90001", "90002", "90003"]
    assert [found.ticket_id for found in second.tickets] == ["90001", "90002", "90003"]


async def test_every_query_is_recorded() -> None:
    """Sprawdza, czy atrapa zapisuje zapytanie w publicznej liście `queries`: po jednym
    wyszukiwaniu jest tam dokładnie to zapytanie.

    Wyłapuje atrapę, która zapytań nie zapisuje: test grafu nie mógłby wtedy sprawdzić, o co
    agent pytał."""
    tool = FakeFindTicketsVectorTool()

    await tool.run(QUERY)

    assert tool.queries == [QUERY]


async def test_the_model_gets_numbers_and_scores_and_nothing_else() -> None:
    """Sprawdza, czy tekst dla modelu to JSON z numerem i podobieństwem każdego z trzech zgłoszeń,
    od najbardziej podobnego, oraz z licznikiem trafień odciętych progiem — i z niczym więcej.

    Wyłapuje wynik wyszukiwania, do którego trafiła treść karty: model mógłby wtedy odpowiedzieć
    bez odczytania karty, a taka odpowiedź nie ma źródła."""
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
    """Sprawdza, czy pusty wynik niesie liczbę trafień odciętych progiem: atrapa ustawiona na brak
    zgłoszeń i trzy odcięte oddaje modelowi pustą listę i liczbę 3.

    Wyłapuje wynik, który gubi ten licznik: agent nie odróżniłby sytuacji „nic nie było" od
    „próg to wyciął"."""
    tool = FakeFindTicketsVectorTool(tickets=[], dropped_below_threshold=3)
    body = json.loads(await tool.run(QUERY))

    assert body == {"tickets": [], "dropped_below_threshold": 3}


def test_the_search_cannot_be_cited() -> None:
    """Sprawdza, czy atrapa wyszukiwania po znaczeniu nie ma metody `cite()`, którą narzędzia
    odczytu podają źródła odpowiedzi.

    Wyłapuje wyszukiwanie, które zaczęło cytować: sam numer zgłoszenia trafiłby wtedy na listę
    źródeł, a źródłem jest dopiero odczytana karta albo wątek."""
    assert not hasattr(FakeFindTicketsVectorTool(), "cite")
