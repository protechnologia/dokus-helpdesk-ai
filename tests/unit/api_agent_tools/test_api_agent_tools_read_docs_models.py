import pytest
from pydantic import ValidationError

from app.agent_tools.docs.read_docs import ReadDocsQuery
from app.agent_tools.docs.read_docs.models import MAX_SECTIONS_PER_READ


def test_a_read_of_nothing_is_refused() -> None:
    """Sprawdza, czy zapytanie z pustą listą identyfikatorów kończy się wyjątkiem `ValidationError`.

    Wyłapuje model, który przepuszcza odczyt niczego: narzędzie oddałoby pusty wynik, jakby wszystko
    było w porządku, choć agent nie wskazał żadnej sekcji."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=[])


def test_a_read_over_the_limit_is_refused() -> None:
    """Sprawdza, czy zapytanie o jedną sekcję więcej, niż pozwala limit (`MAX_SECTIONS_PER_READ`),
    kończy się wyjątkiem `ValidationError`.

    Wyłapuje brak górnej granicy: odczyt ma dobierać sekcje, a bez limitu agent mógłby jednym
    wywołaniem wciągnąć do kontekstu całą instrukcję."""
    too_many = [f"sekcja-{number}" for number in range(MAX_SECTIONS_PER_READ + 1)]

    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=too_many)


def test_a_blank_id_is_refused() -> None:
    """Sprawdza, czy pusty identyfikator na liście, obok poprawnego, kończy się wyjątkiem
    `ValidationError`.

    Wyłapuje model, który przepuszcza pusty identyfikator: taki wpis nie wskazuje żadnej sekcji,
    a zapytanie poszłoby z nim do bazy."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia", ""])


def test_an_unknown_argument_is_refused() -> None:
    """Sprawdza, czy argument spoza schematu (tu `version="4.12"`) kończy się wyjątkiem
    `ValidationError`, jak w każdym modelu zapytania.

    Wyłapuje model, który po cichu ignoruje nieznane argumenty: agent myślałby, że wybrał wydanie
    dokumentu, a narzędzie w ogóle by tego nie uwzględniło."""
    with pytest.raises(ValidationError):
        ReadDocsQuery(section_ids=["adm-kancelaria-edoreczenia"], version="4.12")
