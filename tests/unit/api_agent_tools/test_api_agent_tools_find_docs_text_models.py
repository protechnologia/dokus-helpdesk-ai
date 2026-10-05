import pytest
from pydantic import ValidationError

from app.agent_tools.docs.fake_docs import default_sections
from app.agent_tools.docs.find_docs_text import FindDocsTextQuery
from app.agent_tools.docs.find_docs_text.models import MatchedSection


def test_a_query_with_nothing_to_search_is_refused() -> None:
    """Zapytanie bez `exact` i bez `words` → ValidationError: pusta lista trafień wyglądałaby jak
    „dokumentacja o tym milczy"."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery()


@pytest.mark.parametrize(
    "arguments",
    [{"exact": "Uprawnienia → Kancelaria"}, {"words": "uprawnienie kancelaria"}],
    ids=["exact", "words"],
)
def test_one_field_is_enough(arguments: dict) -> None:
    """Samo `exact` albo samo `words` → poprawne zapytanie: agent podaje to, co ma."""
    assert FindDocsTextQuery(**arguments)


def test_a_too_short_exact_text_is_refused() -> None:
    """Dosłowny ciąg krótszy niż trzy znaki → ValidationError: trafiałby w przypadkowe miejsca."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact="50")


def test_a_phrase_is_measured_and_kept_without_the_spaces_around_it() -> None:
    """Fraza z samych spacji → ValidationError, bo pasowałaby do każdego tekstu; spacje wokół
    frazy → obcięte, żeby nie rozstrzygały o trafieniu."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact="   ")

    assert FindDocsTextQuery(exact="  EDR-0417 ").exact == "EDR-0417"


def test_exact_takes_one_phrase_not_a_list() -> None:
    """Lista fraz w `exact` → ValidationError: jedno wywołanie to jedna fraza, żeby wynik mówił,
    która trafiła."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(exact=["EDR-0417", "Przekaż bufor"])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError: o limicie trafień decyduje konfiguracja."""
    with pytest.raises(ValidationError):
        FindDocsTextQuery(words="uprawnienie", limit=20)


def test_a_matched_section_carries_no_snippet() -> None:
    """Znaleziona sekcja → sposób dopasowania i opis z metryczki, bez pola na fragment treści:
    treść daje wyłącznie odczyt, bo tylko on trafia na listę źródeł."""
    with pytest.raises(ValidationError):
        MatchedSection(matched_by="exact", section=default_sections()[0], snippet="Uprawnienie…")
