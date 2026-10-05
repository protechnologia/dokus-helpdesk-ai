import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorQuery, FoundTicket


@pytest.mark.parametrize("field", ["problem", "symptoms"])
def test_an_empty_query_field_is_refused(field: str) -> None:
    """Sprawdza, czy zapytanie z pustym polem `problem` albo z pustym polem `symptoms` kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje wyszukiwanie z połową zapytania: tekst zapytania składa się z obu pól, tak jak tekst
    zgłoszeń w indeksie, więc bez jednego z nich nie da się go z indeksem porównać."""
    query = {"problem": "Wysyłka ePUAP kończy się błędem", "symptoms": "komunikat o braku sieci"}

    with pytest.raises(ValidationError):
        FindTicketsVectorQuery(**{**query, field: ""})


def test_a_query_with_an_invented_argument_is_refused() -> None:
    """Sprawdza, czy argument, którego zapytanie nie przewiduje (tu `limit=50`), kończy się
    wyjątkiem `ValidationError`.

    Wyłapuje ciche pomijanie nieznanych argumentów: liczbę trafień ustawia konfiguracja, a model,
    który wymyśla własne parametry, ma dostać błąd, żeby było to widać."""
    with pytest.raises(ValidationError):
        FindTicketsVectorQuery(problem="Błąd wysyłki", symptoms="nie dotyczy", limit=50)


def test_a_found_ticket_carries_no_content() -> None:
    """Sprawdza, czy znalezione zgłoszenie przyjmuje tylko numer i podobieństwo: próba dołożenia
    pola `problem` z treścią karty kończy się wyjątkiem `ValidationError`.

    Wyłapuje wynik wyszukiwania, do którego ktoś dołożył treść: kartę i wątek mają dawać
    narzędzia odczytu, bo tylko to, co model odczytał, jest źródłem odpowiedzi."""
    with pytest.raises(ValidationError):
        FoundTicket(ticket_id="33644", score=0.87, problem="Wysyłka ePUAP kończy się błędem")


def test_a_found_ticket_needs_its_number() -> None:
    """Sprawdza, czy znalezione zgłoszenie z pustym numerem kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje trafienie bez numeru oddane modelowi: nie miałby czego podać narzędziu odczytu."""
    with pytest.raises(ValidationError):
        FoundTicket(ticket_id="", score=0.87)
