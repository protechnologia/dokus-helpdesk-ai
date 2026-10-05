from datetime import date

import pytest

from app.agent_tools.tickets.fake_tickets import SIGNING_THREAD, default_threads
from app.agent_tools.tickets.read_tickets_thread import (
    FakeReadTicketsThreadTool,
    ReadTicketsThreadQuery,
    ReadTicketsThreadTool,
    UnknownTicketError,
)
from app.db_postgres import TicketsTable
from tests.helpers_postgres import ScriptedPostgres

# Narzędzie stoi na prawdziwej `TicketsTable`, a podmieniony jest tylko klient bazy — sprawdzamy
# więc, o co narzędzie pyta tabelę i co robi z jej odpowiedzią. Że Postgres oddaje wątek znak
# w znak, sprawdzają testy na stacku.

ROWS = [row.model_dump() for row in default_threads()]

QUERY = ReadTicketsThreadQuery(ticket_id="90011")


def _client() -> ScriptedPostgres:
    """
    Description:
    Klient bez bazy z pięcioma zmyślonymi zgłoszeniami.

    Example args:
        (brak)

    Example result:
        ScriptedPostgres oddający wiersze zgłoszeń po numerach
    """
    return ScriptedPostgres(key="ticket_id", rows=ROWS)


def _tool(
    client: ScriptedPostgres,  # np. _client()
) -> ReadTicketsThreadTool:
    """
    Description:
    Buduje narzędzie na prawdziwej tabeli z klientem-atrapą.

    Example args:
        client=_client()

    Example result:
        ReadTicketsThreadTool odpowiadające bez bazy
    """
    return ReadTicketsThreadTool(tickets=TicketsTable(client))


async def test_the_read_asks_the_table_for_that_one_ticket() -> None:
    """Numer zgłoszenia → jedno zapytanie do tabeli, o ten jeden numer: jedno wywołanie to jeden
    wątek, więc limit wywołań jest limitem wątków przeczytanych w sprawie."""
    client = _client()

    await _tool(client).search(QUERY)

    assert client.calls == [("read", ["90011"])]


async def test_a_thread_comes_back_as_it_was_written() -> None:
    """Wiersz tabeli → numer, data, temat i wątek równy zapisanemu, ze złamaniami linii
    i etykietami komentarzy: model ma przeczytać oryginał, nie streszczenie."""
    thread = await _tool(_client()).search(QUERY)

    assert thread.ticket_id == "90011"
    assert thread.date      == date(2026, 3, 2)
    assert thread.subject   == "Błąd przy podpisie"
    assert thread.thread    == SIGNING_THREAD


async def test_an_unknown_number_is_an_error() -> None:
    """Numer, którego w tabeli nie ma → `UnknownTicketError` z tym numerem: wątek ma każde
    zgłoszenie, więc brak znaczy zły numer, a nie pusty wynik."""
    with pytest.raises(UnknownTicketError) as caught:
        await _tool(_client()).search(ReadTicketsThreadQuery(ticket_id="90019"))

    assert caught.value.ticket_id == "90019"
    assert "90019" in str(caught.value)


async def test_the_thread_that_was_read_is_cited() -> None:
    """Odczytany wątek → jedno źródło z materiału „tickets", z tematem zgłoszenia jako tytułem:
    karty to narzędzie nie zna, więc tytułem nie może być `problem`."""
    tool = _tool(_client())
    refs = tool.cite(await tool.search(QUERY))

    assert [ref.key for ref in refs]   == ["tickets:90011"]
    assert [ref.title for ref in refs] == ["Błąd przy podpisie"]


async def test_the_tool_and_its_fake_tell_the_model_the_same() -> None:
    """To samo zgłoszenie w tabeli i w atrapie → ten sam tekst dla modelu i to samo źródło: test
    grafu na atrapie sprawdza to, co model dostanie na produkcji."""
    real = _tool(_client())
    fake = FakeReadTicketsThreadTool()

    real_result = await real.search(QUERY)
    fake_result = await fake.search(QUERY)

    assert real.render_for_model(real_result) == fake.render_for_model(fake_result)
    assert real.cite(real_result)             == fake.cite(fake_result)


async def test_aclose_closes_the_database_client() -> None:
    """`aclose()` → zamknięty klient Postgresa: sprzątający nie musi wiedzieć, z czego narzędzie
    jest zbudowane."""
    client = _client()

    await _tool(client).aclose()

    assert client.closed
