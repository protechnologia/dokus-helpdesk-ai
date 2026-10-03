import pytest
from pydantic import ValidationError

from app.tools.find_tickets_vector import FindTicketsVectorQuery, FoundTicket

# Zgłoszenie z prawdziwą treścią — w kształcie, w jakim `TicketPoint.from_ticket` zapisuje payload.
VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "pytano o wersję przeglądarki",
}


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


def test_the_ticket_is_validated_by_its_own_contract() -> None:
    """Payload bez pola ParsedTicket → ValidationError: treść sprawdza ten sam kontrakt, który
    wpuścił ją do indeksu, a nie dopiero prompt."""
    incomplete = {key: value for key, value in VALID_TICKET.items() if key != "cause"}

    with pytest.raises(ValidationError):
        FoundTicket(score=0.87, ticket=incomplete)


def test_a_valid_ticket_is_kept_whole() -> None:
    """Kompletny payload → znalezione zgłoszenie, z którego `cite()` odczyta id i datę wprost,
    bez kopii trzymanych obok."""
    found = FoundTicket(score=0.87, ticket=VALID_TICKET)

    assert found.ticket.ticket_id        == "33644"
    assert found.ticket.date.isoformat() == "2026-03-14"
