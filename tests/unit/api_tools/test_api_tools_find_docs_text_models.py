import pytest
from pydantic import ValidationError

from app.tools.docs.find_docs_text import FindDocsTextQuery


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Zapytanie bez `exact` i bez `words` → ValidationError: pusta lista trafień wyglądałaby jak
    „dokumentacja o tym milczy"."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": ["Uprawnienia → Kancelaria"]}, {"words": "uprawnienie kancelaria"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Samo `exact` albo samo `words` → poprawne zapytanie: agent podaje to, co ma."""
    assert FindDocsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Dosłowny ciąg krótszy niż trzy znaki → ValidationError: trafiałby w przypadkowe miejsca."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact=["50"])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: o limicie trafień decyduje konfiguracja."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(words="uprawnienie", limit=20)
