from dataclasses import dataclass

from tests._helpers.golden_tickets.models.golden_query import GoldenQuery


@dataclass(frozen=True)
class GoldenTicket:
    """Wpis golden setu: zgłoszenie korpusu odniesienia z etykietą przeglądu i zapytaniem."""

    ticket_id:     str                 # numer zgłoszenia, jak w karcie
    useful:        bool                # czy karta niesie wiedzę, jak pole karty o tej nazwie
    useful_reason: str                 # dlaczego, jednym zdaniem
    query:         GoldenQuery | None  # zapytanie, którego celem jest to zgłoszenie, jeśli jest
