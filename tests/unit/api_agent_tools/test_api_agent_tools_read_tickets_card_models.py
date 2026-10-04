import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_card import ReadTicketsCardQuery
from app.agent_tools.tickets.read_tickets_card.models import MAX_CARDS_PER_READ


def test_a_read_of_nothing_is_refused() -> None:
    """Pusta lista numerów → ValidationError: nie ma czego odczytać."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=[])


def test_a_read_over_the_limit_is_refused() -> None:
    """Więcej numerów niż limit → ValidationError: odczyt ma objąć znalezione zgłoszenia, a nie
    wciągać do kontekstu pół bazy."""
    too_many = [str(number) for number in range(MAX_CARDS_PER_READ + 1)]

    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=too_many)


def test_the_limit_fits_several_searches_at_once() -> None:
    """Limit kart → co najmniej tyle, ile dają trzy wyszukiwania po pięć trafień: model ma czytać
    karty wszystkich znalezionych zgłoszeń, także z kilku zapytań naraz."""
    assert MAX_CARDS_PER_READ >= 15


def test_a_blank_number_is_refused() -> None:
    """Pusty numer → ValidationError: nie wskazuje żadnego zgłoszenia."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=["90001", ""])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError, jak w każdym modelu zapytania."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=["90001"], fields=["cause"])
