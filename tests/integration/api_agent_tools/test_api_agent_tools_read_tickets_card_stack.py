"""
Description:
Test integracyjny narzędzia `read_tickets_card` z prawdziwym embedderem i Qdrantem: czy numery
oddane przez wyszukiwanie dają się odczytać jako karty równe zaindeksowanym. Wymaga działającego
stacku.

| scenariusz                       | oczekiwanie                                    |
|----------------------------------|------------------------------------------------|
| odczyt kart znalezionych numerów | karty równe zapisanym, w kolejności wyszukania |
| odczyt numeru spoza kolekcji     | numer na liście „bez karty", nie błąd          |

Indeks buduje fixture `tickets_cards` z `conftest.py` tego folderu: trzy zmyślone karty
zaindeksowane produkcyjnym `TicketsIndexer`.

O czym pamiętać przy zmianach:

- Odczyt dostaje numery od wyszukiwania, nie wpisane w teście: sprawdzamy, że oba narzędzia
  mówią o tych samych numerach.
- Asercje są na równość kart: payload z Qdranta ma wrócić do `ParsedTicket` bez strat.
"""

import pytest

from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorQuery
from app.agent_tools.tickets.read_tickets_card import ReadTicketsCardQuery

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


async def test_found_numbers_read_back_as_the_cards_that_were_indexed(tickets_cards) -> None:
    """Numery z wyszukiwania podane odczytowi → karty równe zaindeksowanym, w kolejności
    wyszukania: payload z Qdranta wraca do `ParsedTicket` bez strat, a oba narzędzia mówią o tych
    samych numerach."""
    first = tickets_cards.cards[0]

    found  = await tickets_cards.find.find(
        FindTicketsVectorQuery(problem=first.problem, symptoms=first.symptoms)
    )
    wanted = [ticket.ticket_id for ticket in found.tickets]
    result = await tickets_cards.read.search(ReadTicketsCardQuery(ticket_ids=wanted))

    indexed = {card.ticket_id: card for card in tickets_cards.cards}

    assert result.cards        == [indexed[ticket_id] for ticket_id in wanted]
    assert result.without_card == []
    assert [ref.item_id for ref in tickets_cards.read.cite(result)] == wanted


async def test_a_number_outside_the_collection_comes_back_without_a_card(tickets_cards) -> None:
    """Numer, którego w kolekcji nie ma → lista „bez karty", a karta znanego numeru wraca
    normalnie: Qdrant nie zgłasza błędu przy brakującym punkcie, więc narzędzie mówi o tym samo."""
    known  = tickets_cards.cards[1]
    result = await tickets_cards.read.search(
        ReadTicketsCardQuery(ticket_ids=["99999", known.ticket_id])
    )

    assert result.cards        == [known]
    assert result.without_card == ["99999"]
