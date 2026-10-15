import dataclasses


@dataclasses.dataclass(frozen=True)
class TicketsVectorMeasurement:
    """Wynik jednego przejścia golden setu i dystraktorów przez `find_tickets_vector`."""

    target_first:          int  # zapytania, na które rekord-cel wrócił jako pierwszy
    target_returned:       int  # zapytania, na które rekord-cel wrócił na dowolnym miejscu
    distractors_with_hits: int  # dystraktory z co najmniej jednym trafieniem
