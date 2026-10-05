import json

from app.agent_tools.tickets.fake_tickets import default_threads
from app.agent_tools.tickets.find_tickets_text import (
    FakeFindTicketsTextTool,
    FindTicketsTextQuery,
    FindTicketsTextTool,
)
from app.db_postgres import TicketsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `TicketsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedziami. Że Postgres naprawdę tak
# dopasowuje, sprawdzają testy na stacku.

ROWS = [row.model_dump() for row in default_threads()]

MESSAGE = "Nie udało się skomunikować z serwerem"


def _client(
    substring: dict[str, list[str]] | None = None,  # np. {"ORA-00942": ["90011"]}
    words:     dict[str, list[str]] | None = None,  # np. {"załącznik limit": ["90003"]}
) -> ScriptedPostgres:
    """
    Description:
    Klient bez bazy ze zmyślonymi zgłoszeniami: na frazę i na słowa oddaje ustalone numery.

    Example args:
        substring={"ORA-00942": ["90011"]}
        words={"załącznik limit": ["90003"]}

    Example result:
        ScriptedPostgres odpowiadający jednym numerem na frazę „ORA-00942"
    """
    return ScriptedPostgres(key="ticket_id", rows=ROWS, substring=substring, words=words)


def _tool(
    client: ScriptedPostgres,  # np. _client(words={"załącznik limit": ["90003"]})
    limit:  int = 5,           # np. 5 — RAG_TOP_K
) -> FindTicketsTextTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=_client(words={"załącznik limit": ["90003"]})

    Example result:
        FindTicketsTextTool odpowiadające bez bazy
    """
    return FindTicketsTextTool(tickets=TicketsTable(client), limit=limit)


async def test_the_phrase_goes_by_substring_and_the_words_by_dictionary() -> None:
    """Sprawdza, czy zapytanie z frazą `SQLSTATE[23000]` i słowami „załącznik limit" daje dwa
    zapytania do tabeli: frazę szukaną jako dosłowny podciąg i słowa szukane przez słownik.

    Wyłapuje zamianę dróg albo wartości: kod błędu ma być szukany dosłownie, a słowa w dowolnej
    odmianie, więc po zamianie oba wyszukiwania gubiłyby trafienia."""
    client = _client()

    await _tool(client).find(FindTicketsTextQuery(exact="SQLSTATE[23000]", words="załącznik limit"))

    assert client.calls == [
        ("substring", "SQLSTATE[23000]"),
        ("words",     "załącznik limit"),
    ]


async def test_a_field_that_was_not_given_is_not_searched() -> None:
    """Sprawdza, czy narzędzie pyta tabelę tylko o to pole, które agent podał: sama fraza daje
    jedno zapytanie o podciąg, a same słowa jedno zapytanie przez słownik.

    Wyłapuje narzędzie, które pyta bazę także o pole puste: do tabeli szłoby wtedy zapytanie bez
    wartości, zamiast pominięcia tej drogi."""
    only_exact = _client()
    only_words = _client()

    await _tool(only_exact).find(FindTicketsTextQuery(exact="ORA-00942"))
    await _tool(only_words).find(FindTicketsTextQuery(words="załącznik"))

    assert [kind for kind, _ in only_exact.calls] == ["substring"]
    assert [kind for kind, _ in only_words.calls] == ["words"]


async def test_either_field_is_enough_for_a_ticket_to_come_back() -> None:
    """Sprawdza, czy wyniki obu pól się sumują: fraza trafia w zgłoszenia `90011` i `90012`,
    słowa w `90003`, a w wyniku są wszystkie trzy, znalezione frazą pierwsze.

    Wyłapuje narzędzie, które oddaje tylko zgłoszenia pasujące do obu pól naraz: pola szukają
    niezależnie, więc zgłoszenie znalezione jedną drogą nie może zniknąć z wyniku."""
    client = _client(substring={MESSAGE: ["90011", "90012"]}, words={"załącznik": ["90003"]})

    result = await _tool(client).find(FindTicketsTextQuery(exact=MESSAGE, words="załącznik"))

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90011", "exact"),
        ("90012", "exact"),
        ("90003", "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_ticket_found_both_ways_comes_back_once_as_exact() -> None:
    """Sprawdza, czy zgłoszenie znalezione i frazą, i słowami (tu `90011`) jest w wyniku raz,
    z etykietą `exact`, a licznik pominiętych zostaje na zerze.

    Wyłapuje zgłoszenie powtórzone w wyniku albo policzone dwa razy: zajmowałoby dwa miejsca
    w limicie i zawyżało liczbę pominiętych."""
    client = _client(substring={MESSAGE: ["90011"]}, words={"załącznik": ["90003", "90011"]})

    result = await _tool(client).find(FindTicketsTextQuery(exact=MESSAGE, words="załącznik"))

    assert [(found.ticket_id, found.matched_by) for found in result.tickets] == [
        ("90011", "exact"),
        ("90003", "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_matches_over_the_limit_are_counted() -> None:
    """Sprawdza, czy przy pięciu pasujących zgłoszeniach i limicie 2 wynik ma dwa pierwsze numery,
    a pozostałe trzy są policzone jako pominięte.

    Wyłapuje wynik ucięty bez śladu: „pokazano dwa z pięciu" mówi agentowi, że zapytanie było
    zbyt ogólne, a bez licznika wyglądałoby, że pasują tylko dwa zgłoszenia."""
    numbers = ["90001", "90002", "90003", "90011", "90012"]
    client  = _client(words={"zgłoszenie": numbers})

    result = await _tool(client, limit=2).find(FindTicketsTextQuery(words="zgłoszenie"))

    assert [found.ticket_id for found in result.tickets] == ["90001", "90002"]
    assert result.omitted_over_limit == 3


async def test_the_model_gets_numbers_and_nothing_is_read() -> None:
    """Sprawdza, czy model dostaje sam numer znalezionego zgłoszenia i to, czym je znaleziono,
    a narzędzie zadaje tabeli tylko jedno zapytanie, o podciąg — wątku w ogóle nie czyta.

    Wyłapuje wyszukiwanie, które czyta wątki i dokłada ich treść do wyniku: treść mają dawać
    narzędzia odczytu, bo tylko one podają źródła odpowiedzi."""
    client = _client(substring={MESSAGE: ["90011"]})

    text = await _tool(client).run(FindTicketsTextQuery(exact=MESSAGE))

    assert json.loads(text) == {
        "tickets":            [{"ticket_id": "90011", "matched_by": "exact"}],
        "omitted_over_limit": 0,
    }
    assert [kind for kind, _ in client.calls] == ["substring"]


async def test_nothing_found_is_an_empty_result() -> None:
    """Sprawdza, czy zapytanie, do którego nie pasuje żaden wątek, daje pusty wynik: bez zgłoszeń
    i z zerem pominiętych.

    Wyłapuje narzędzie, które brak trafień zgłasza jako błąd: „niczego takiego nie było" to
    poprawna odpowiedź wyszukiwania."""
    result = await _tool(_client()).find(FindTicketsTextQuery(exact="KSeF-500", words="faktura"))

    assert result.tickets            == []
    assert result.omitted_over_limit == 0


async def test_the_tool_and_its_fake_tell_the_model_the_same() -> None:
    """Sprawdza, czy narzędzie i jego atrapa dają modelowi ten sam tekst, gdy mają te same
    trafienia: zgłoszenie `90011` znalezione frazą i `90012` znalezione słowami.

    Wyłapuje rozjazd między narzędziem a atrapą: testy grafów na atrapie sprawdzałyby wtedy inny
    tekst niż ten, który model dostaje na produkcji."""
    client = _client(substring={MESSAGE: ["90011"]}, words={"sekwencja": ["90012"]})
    query  = FindTicketsTextQuery(exact=MESSAGE, words="sekwencja")

    real = await _tool(client).run(query)
    fake = await FakeFindTicketsTextTool().run(query)

    assert real == fake


async def test_aclose_closes_the_database_client() -> None:
    """Sprawdza, czy `aclose()` narzędzia zamyka klienta Postgresa, na którym ono stoi.

    Wyłapuje połączenie z bazą zostawione otwarte: sprzątający woła tylko `aclose()` narzędzia
    i nie wie, z czego jest ono zbudowane, więc sam klienta nie zamknie."""
    client = _client()

    await _tool(client).aclose()

    assert client.closed
