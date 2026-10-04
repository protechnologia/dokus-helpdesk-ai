import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorQuery, FoundTicket


@pytest.mark.parametrize("field", ["problem", "symptoms"])
def test_an_empty_query_field_is_refused(field: str) -> None:
    """Puste `problem` albo `symptoms` → ValidationError: z połowy kształtu korpusu nie da się
    złożyć tekstu porównywalnego z indeksem."""
    query = {"problem": "Wysyłka ePUAP kończy się błędem", "symptoms": "komunikat o braku sieci"}

    with pytest.raises(ValidationError):
        FindTicketsVectorQuery(**{**query, field: ""})


def test_a_query_with_an_invented_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: liczbę trafień ustawia konfiguracja, a model
    wymyślający parametry ma być widoczny, nie po cichu pominięty."""
    with pytest.raises(ValidationError):
        FindTicketsVectorQuery(problem="Błąd wysyłki", symptoms="nie dotyczy", limit=50)


def test_a_found_ticket_carries_no_content() -> None:
    """Znalezione zgłoszenie → numer i podobieństwo, bez pola na treść: kartę i wątek dają
    odczyty, a tylko odczyt jest źródłem."""
    with pytest.raises(ValidationError):
        FoundTicket(ticket_id="33644", score=0.87, problem="Wysyłka ePUAP kończy się błędem")


def test_a_found_ticket_needs_its_number() -> None:
    """Pusty numer zgłoszenia → ValidationError: bez numeru nie ma czego odczytać."""
    with pytest.raises(ValidationError):
        FoundTicket(ticket_id="", score=0.87)
