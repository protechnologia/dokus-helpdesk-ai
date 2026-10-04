import pytest
from pydantic import ValidationError

from app.agent_tools.docs.read_docs import ReadDocsQuery
from app.agent_tools.docs.read_docs.models import MAX_SECTIONS_PER_READ


def test_a_read_of_nothing_is_refused() -> None:
    """Pusta lista identyfikatorów → ValidationError: nie ma czego odczytać."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=[])


def test_a_read_over_the_limit_is_refused() -> None:
    """Więcej identyfikatorów niż limit → ValidationError: odczyt ma dobierać sekcje, a nie
    wciągać do kontekstu całą instrukcję."""
    too_many = [f"sekcja-{number}" for number in range(MAX_SECTIONS_PER_READ + 1)]

    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=too_many)


def test_a_blank_id_is_refused() -> None:
    """Pusty identyfikator → ValidationError: nie wskazuje żadnej sekcji."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia", ""])


def test_an_unknown_argument_is_refused() -> None:
    """Argument spoza schematu → ValidationError, jak w każdym modelu zapytania."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"], version="4.12")
