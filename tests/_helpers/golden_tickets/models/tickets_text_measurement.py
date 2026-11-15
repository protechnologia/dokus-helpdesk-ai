import dataclasses


@dataclasses.dataclass(frozen=True)
class TicketsTextMeasurement:
    """Wynik jednego przejścia zestawu tekstowego przez `find_tickets_text`."""

    target_first:          int  # zapytania, na które zgłoszenie-cel wróciło jako pierwsze
    target_returned:       int  # zapytania, na które zgłoszenie-cel wróciło na dowolnym miejscu
    distractors_with_hits: int  # zapytania bez celu z co najmniej jednym trafieniem
