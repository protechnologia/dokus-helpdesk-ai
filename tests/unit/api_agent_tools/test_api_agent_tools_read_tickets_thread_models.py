import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_thread import ReadTicketsThreadQuery
from app.agent_tools.tickets.read_tickets_thread.models import MAX_THREADS_PER_READ


def test_a_read_of_nothing_is_refused() -> None:
    """Pusta lista numerów → ValidationError: nie ma czego odczytać."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=[])


def test_a_read_over_the_limit_is_refused() -> None:
    """Więcej numerów niż limit → ValidationError: wątki są długie, więc model ma czytać te,
    które wybrał, a nie wszystko, co znalazł."""
    too_many = [str(number) for number in range(MAX_THREADS_PER_READ + 1)]

    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=too_many)


def test_a_blank_number_is_refused() -> None:
    """Pusty numer → ValidationError: nie wskazuje żadnego zgłoszenia."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=["90011", ""])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError, jak w każdym modelu zapytania."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=["90011"], max_length=2000)
