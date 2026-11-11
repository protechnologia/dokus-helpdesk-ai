"""
Description:
Atrapy zależności indeksera zgłoszeń i serwisu zamkniętego zgłoszenia (embedder, kolekcja
zgłoszeń, tabela wątków). Używają ich testy `TicketsIndexer` i `ClosedTicketIndexer`.

Logika leży w `helper.py`, stałe w `constants.py`; testy importują je z pakietu. Próbki
zamkniętego zgłoszenia leżą w `samples.py` i test bierze je z modułu.
"""

from tests._helpers.tickets_index.constants import VECTOR_SIZE
from tests._helpers.tickets_index.helper import (
    FakeEmbedder,
    FakeThreads,
    FakeTickets,
    closed_ticket_indexer_on,
)

__all__ = [
    "VECTOR_SIZE",
    "FakeEmbedder",
    "FakeThreads",
    "FakeTickets",
    "closed_ticket_indexer_on",
]
