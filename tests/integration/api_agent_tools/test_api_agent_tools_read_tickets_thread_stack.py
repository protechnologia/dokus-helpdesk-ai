"""
Description:
Test integracyjny narzędzia `read_tickets_thread` z prawdziwym Postgresem: czy numer oddany przez
wyszukiwanie daje się odczytać i czy wątek wraca taki, jak go zapisano. Wymaga działającego
stacku.

| scenariusz                                    | oczekiwanie                          |
|-----------------------------------------------|--------------------------------------|
| numer znaleziony frazą złamaną w wątku        | wątek znak w znak, ze złamaniem      |
| numer, którego w tabeli nie ma                | błąd z tym numerem, nie pusty wynik  |

Tabelę buduje fixture `tickets_threads` z `conftest.py` tego folderu: pięć zmyślonych wątków
z zestawu atrap.

O czym pamiętać przy zmianach:

- Odczyt dostaje numer od wyszukiwania, nie wpisany w teście: sprawdzamy, że oba narzędzia mówią
  o tym samym zgłoszeniu.
- Jedno wywołanie to jeden wątek; kilka wątków to kilka wywołań.
- Na prawdziwych wątkach narzędzie ruszy dopiero po anonimizacji (p. 19) i masowym imporcie
  (p. 31); do tego czasu to jedyne sprawdzenie na bazie.
"""

import pytest

from app.agent_tools.tickets.find_tickets_text import FindTicketsTextQuery
from app.agent_tools.tickets.read_tickets_thread import (
    ReadTicketsThreadQuery,
    UnknownTicketError,
)

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]


async def test_a_ticket_found_by_a_broken_phrase_is_read_verbatim(tickets_threads) -> None:
    """Sprawdza, czy zdanie zapisane w wątku w dwóch liniach (złamane po słowie „zaległe") da się
    znaleźć frazą wpisaną w jednej linii i czy odczyt znalezionego numeru oddaje wątek znak
    w znak tak, jak go zapisano: ze złamaniem linii, z tematem i z datą zgłoszenia.

    Wyłapuje dwie usterki: wyszukiwanie, któremu złamanie linii zasłania zdanie, oraz odczyt,
    który oddaje tekst przygotowany dla wyszukiwania (ze spacjami zamiast złamań) zamiast
    oryginalnego wątku."""
    found = await tickets_threads.find.find(
        FindTicketsTextQuery(exact="zaległe przesyłki pobrały się same")
    )

    assert [item.ticket_id for item in found.tickets] == ["90001"]

    read    = await tickets_threads.read.search(
        ReadTicketsThreadQuery(ticket_id=found.tickets[0].ticket_id)
    )
    written = next(row for row in tickets_threads.rows if row.ticket_id == "90001")

    assert read.thread  == written.thread
    assert read.subject == "Brak przesyłek z e-Doręczeń"
    assert read.date    == written.ticket_date
    assert "zaległe\nprzesyłki" in read.thread


async def test_a_number_the_table_does_not_have_is_an_error(tickets_threads) -> None:
    """Sprawdza, czy odczyt wątku o numerze, którego w tabeli nie ma (99999), kończy się błędem
    `UnknownTicketError` z tym numerem.

    Wyłapuje pusty wynik w miejscu błędu: baza oddaje wtedy zero wierszy i sama niczego nie
    zgłasza, więc bez sprawdzenia w narzędziu model nie dowiedziałby się, że podał zły numer."""
    with pytest.raises(UnknownTicketError) as caught:
        await tickets_threads.read.search(ReadTicketsThreadQuery(ticket_id="99999"))

    assert caught.value.ticket_id == "99999"
