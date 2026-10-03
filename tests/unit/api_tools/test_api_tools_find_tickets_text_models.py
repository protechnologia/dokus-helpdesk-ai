import pytest
from pydantic import ValidationError

from app.tools.tickets.find_tickets_text import FindTicketsTextQuery


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Zapytanie bez `exact` i bez `words` → ValidationError: pusta lista trafień wyglądałaby jak
    „niczego takiego nie było"."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": ["SQLSTATE[23000]"]}, {"words": "załącznik limit"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Samo `exact` albo samo `words` → poprawne zapytanie: agent podaje to, co ma."""
    assert FindTicketsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Dosłowny ciąg krótszy niż trzy znaki → ValidationError: „50" trafia w numery telefonów
    i daty, a takie trafienie wygląda na odpowiedź."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(exact=["50"])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: o limicie trafień decyduje konfiguracja."""
    with pytest.raises(ValidationError):
        FindTicketsTextQuery(words="załącznik", limit=20)
