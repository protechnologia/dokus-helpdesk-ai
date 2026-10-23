from dataclasses import dataclass

from tests._helpers.golden_tickets.models.golden_ticket import GoldenTicket


@dataclass(frozen=True)
class GoldenSet:
    """Golden set zgłoszeń z pliku: liczniki z metryczki i wpisy w kolejności z pliku."""

    counts:  dict[str, int]      # liczniki z metryczki: `useful`, `not_useful`, `queries`
    tickets: list[GoldenTicket]  # wpis na każde zgłoszenie korpusu odniesienia
