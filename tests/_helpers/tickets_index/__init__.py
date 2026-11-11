"""
Description:
Atrapy zależności indeksera zgłoszeń i serwisu zamkniętego zgłoszenia (embedder, kolekcja
zgłoszeń, tabela wątków) oraz aplikacja trasy `POST /tickets/closed` na nich. Używają ich testy
`TicketsIndexer`, `ClosedTicketIndexer` i tej trasy.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują je z pakietu. Próbki
zamkniętego zgłoszenia leżą w `samples.py` i test bierze je z modułu.
"""

from tests._helpers.tickets_index.constants import GRAPH_NODES, VECTOR_SIZE
from tests._helpers.tickets_index.helper import (
    FakeEmbedder,
    FakeThreads,
    FakeTickets,
    ReplacingAnonymizer,
    app_closing_tickets,
    card_graph,
    closed_ticket_indexer_on,
)

__all__ = [
    "GRAPH_NODES",
    "VECTOR_SIZE",
    "FakeEmbedder",
    "FakeThreads",
    "FakeTickets",
    "ReplacingAnonymizer",
    "app_closing_tickets",
    "card_graph",
    "closed_ticket_indexer_on",
]
