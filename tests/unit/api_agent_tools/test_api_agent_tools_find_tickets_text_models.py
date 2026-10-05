import pytest
from pydantic import ValidationError

from app.agent_tools.tickets.find_tickets_text import FindTicketsTextQuery, MatchedTicket


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Zapytanie bez `exact` i bez `words` → ValidationError: pusta lista trafień wyglądałaby jak
    „niczego takiego nie było"."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": "SQLSTATE[23000]"}, {"words": "załącznik limit"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Samo `exact` albo samo `words` → poprawne zapytanie: agent podaje to, co ma."""
    assert FindTicketsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Dosłowny ciąg krótszy niż trzy znaki → ValidationError: „50" trafia w numery telefonów
    i daty, a takie trafienie wygląda na odpowiedź."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(exact="50")


def test_exact_takes_one_phrase_not_a_list() -> None:
    """Lista fraz w `exact` → ValidationError: jedno wywołanie to jedna fraza, żeby wynik mówił,
    która trafiła."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(exact=["SQLSTATE[23000]", "ORA-00942"])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: o limicie trafień decyduje konfiguracja."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(words="załącznik", limit=20)


def test_a_matched_ticket_carries_no_content() -> None:
    """Znalezione zgłoszenie → numer i sposób dopasowania, bez pola na wątek ani fragment: treść
    daje wyłącznie odczyt, bo tylko on trafia na listę źródeł."""
    with pytest.raises(ValidationError):
        MatchedTicket(ticket_id="90011", matched_by="exact", thread="ZGŁOSZENIE 90011…")


def test_a_match_kind_outside_the_query_fields_is_refused() -> None:
    """Sposób dopasowania spoza `exact` i `words` → ValidationError: etykieta ma nosić nazwę
    pola, którym agent pytał."""
    with pytest.raises(ValidationError):
        MatchedTicket(ticket_id="90011", matched_by="phrase")
