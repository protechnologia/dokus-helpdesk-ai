import pytest
from pydantic import ValidationError

from app.tools.fake_docs import default_sections
from app.tools.find_docs_vector import FindDocsVectorQuery, FoundSection


def test_an_empty_query_is_refused() -> None:
    """Zapytanie bez tekstu → ValidationError: nie ma czego dopasować do sekcji."""
    with pytest.raises(ValidationError):
        FindDocsVectorQuery(text="")


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: liczbę trafień i próg ustawia konfiguracja."""
    with pytest.raises(ValidationError):
        FindDocsVectorQuery(text="uprawnienia", limit=20)


def test_a_found_section_carries_no_content() -> None:
    """Znaleziona sekcja → podobieństwo i opis z metryczki, bez pola na treść: treść daje dopiero
    odczyt, a tylko odczyt jest źródłem."""
    with pytest.raises(ValidationError):
        FoundSection(score=0.74, section=default_sections()[0], text="Uprawnienie nadaje…")
