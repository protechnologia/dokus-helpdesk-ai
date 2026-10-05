import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_thread import ReadTicketsThreadQuery


def test_a_read_takes_one_number() -> None:
    """Sprawdza, czy zapytanie z jednym numerem zgłoszenia jest poprawne i zachowuje ten numer.

    Wyłapuje zmianę kształtu zapytania, po której zwykłe wywołanie z jednym numerem przestaje
    działać: jedno wywołanie ma czytać jeden wątek."""
    assert ReadTicketsThreadQuery(ticket_id="90011").ticket_id == "90011"


def test_a_list_of_numbers_is_refused() -> None:
    """Sprawdza, czy zapytanie z listą numerów kończy się `ValidationError`, zarówno gdy lista stoi
    w polu `ticket_id`, jak i w polu `ticket_ids`.

    Wyłapuje powrót do czytania kilku wątków jednym wywołaniem: wątki są długie, a limit wywołań ma
    być limitem wątków, więc kilka wątków to kilka wywołań."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id=["90011", "90012"])

    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_ids=["90011", "90012"])


def test_a_blank_number_is_refused() -> None:
    """Sprawdza, czy zapytanie z pustym numerem zgłoszenia kończy się `ValidationError`.

    Wyłapuje pusty numer przyjęty jako poprawny: nie wskazuje żadnego zgłoszenia, więc narzędzie
    szukałoby w bazie zgłoszenia bez numeru."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id="")


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy zapytanie z argumentem spoza schematu (tu `max_length`) kończy się
    `ValidationError`.

    Wyłapuje zapytanie, które po cichu pomija nieznane argumenty: agent, który wymyślił argument, na
    przykład limit długości wątku, nie dowiedziałby się, że nic on nie zmienił."""
    with pytest.raises(ValidationError):
        ReadTicketsThreadQuery(ticket_id="90011", max_length=2000)
