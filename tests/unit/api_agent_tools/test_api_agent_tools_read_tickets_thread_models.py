import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_thread import ReadTicketsThreadQuery


def test_a_read_takes_one_number() -> None:
    """Jeden numer → poprawne zapytanie: jedno wywołanie to jeden wątek."""
    assert ReadTicketsThreadQuery(ticket_id="90011").ticket_id == "90011"


def test_a_list_of_numbers_is_refused() -> None:
    """Lista numerów → ValidationError: wątki są długie, a limit wywołań ma być limitem wątków,
    więc kilka wątków to kilka wywołań."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id=["90011", "90012"])

    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=["90011", "90012"])


def test_a_blank_number_is_refused() -> None:
    """Pusty numer → ValidationError: nie wskazuje żadnego zgłoszenia."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id="")


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError, jak w każdym modelu zapytania."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id="90011", max_length=2000)
