import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_card import ReadTicketsCardQuery
from app.agent_tools.tickets.read_tickets_card.models import MAX_CARDS_PER_READ


def test_a_read_of_nothing_is_refused() -> None:
    """Sprawdza, czy zapytanie z pustą listą numerów zgłoszeń kończy się `ValidationError`.

    Wyłapuje zapytanie bez numerów przyjęte jako poprawne: nie ma w nim czego odczytać, więc agent
    ma dostać błąd, a nie pusty wynik wyglądający jak brak kart."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=[])


def test_a_read_over_the_limit_is_refused() -> None:
    """Sprawdza, czy zapytanie z liczbą numerów o jeden większą niż limit kart na jedno wywołanie
    kończy się `ValidationError`.

    Wyłapuje zdjęty limit: odczyt ma objąć znalezione zgłoszenia, a bez limitu jedno wywołanie
    mogłoby wciągnąć do kontekstu modelu pół bazy."""
    too_many = [str(number) for number in range(MAX_CARDS_PER_READ + 1)]

    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=too_many)


def test_the_limit_fits_several_searches_at_once() -> None:
    """Sprawdza, czy limit kart na jedno wywołanie wynosi co najmniej 15, czyli tyle, ile dają trzy
    wyszukiwania po pięć trafień.

    Wyłapuje limit obniżony tak, że model nie przeczyta jednym wywołaniem kart wszystkich
    znalezionych zgłoszeń, gdy pochodzą z kilku zapytań."""
    assert MAX_CARDS_PER_READ >= 15


def test_a_blank_number_is_refused() -> None:
    """Sprawdza, czy zapytanie, w którym jeden z numerów jest pustym napisem, kończy się
    `ValidationError`.

    Wyłapuje pusty numer przyjęty jako poprawny: nie wskazuje żadnego zgłoszenia, więc wróciłby jako
    zgłoszenie bez karty zamiast jako błąd wywołania."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=["90001", ""])


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy zapytanie z argumentem spoza schematu (tu `fields`) kończy się
    `ValidationError`.

    Wyłapuje zapytanie, które po cichu pomija nieznane argumenty: agent, który wymyślił argument,
    nie dowiedziałby się, że nic on nie zmienił."""
    with pytest.raises(ValidationError):
        ReadTicketsCardQuery(ticket_ids=["90001"], fields=["cause"])
