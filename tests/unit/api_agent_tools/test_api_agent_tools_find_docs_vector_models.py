import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery, FoundSection


def test_an_empty_query_is_refused() -> None:
    """Sprawdza, czy zapytanie z pustym tekstem kończy się wyjątkiem `ValidationError`.

    Wyłapuje model, który przepuszcza puste zapytanie: do wyszukiwania poszedłby tekst, w którym nie
    ma czego dopasować do sekcji."""
    with pytest.raises(ValidationError):
        FindDocsVectorQuery(text="")


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy argument spoza schematu (tu `limit=20`) kończy się wyjątkiem `ValidationError`.

    Wyłapuje model, który po cichu ignoruje nieznane argumenty: agent myślałby, że sam ustawił
    liczbę trafień, a ją i próg podobieństwa ustawia konfiguracja."""
    with pytest.raises(ValidationError):
        FindDocsVectorQuery(text="uprawnienia", limit=20)


def test_a_found_section_carries_no_content() -> None:
    """Sprawdza, czy znalezionej sekcji nie da się zbudować z dodatkowym polem na treść (`text`):
    taka próba kończy się wyjątkiem `ValidationError`.

    Wyłapuje treść dołożoną do wyniku wyszukiwania: treść ma dawać dopiero odczyt sekcji, bo tylko
    odczytana sekcja jest źródłem odpowiedzi."""
    with pytest.raises(ValidationError):
        FoundSection(score=0.74, section=default_sections()[0], text="Uprawnienie nadaje…")
