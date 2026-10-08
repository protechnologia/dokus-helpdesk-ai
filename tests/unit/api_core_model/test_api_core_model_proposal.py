import pytest
from pydantic import ValidationError

from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes


def test_notes_may_be_empty() -> None:
    """Sprawdza, czy propozycja z pustymi uwagami dla wdrożeniowca jest poprawna.

    Wyłapuje walidację, która żąda uwag zawsze: model musiałby je wymyślać także w sprawie, w której
    nie ma nic do dodania, a odpowiedź bez nich wracałaby do poprawki."""
    assert Proposal(text="1. Od kiedy?", internal_notes="").internal_notes == ""


def test_a_proposal_without_notes_is_rejected() -> None:
    """Sprawdza, czy odpowiedź modelu bez pola `internal_notes` daje błąd walidacji, choć to pole
    może być puste.

    Wyłapuje pole, które model może pominąć: nie dałoby się odróżnić modelu, który nie miał uwag,
    od takiego, który o nich zapomniał."""
    with pytest.raises(ValidationError):
        Proposal.model_validate({"text": "1. Od kiedy?"})


def test_the_text_for_the_client_may_not_be_empty() -> None:
    """Sprawdza, czy propozycja z pustą treścią dla klienta daje błąd walidacji.

    Wyłapuje propozycję bez treści przyjętą jako poprawną: treść dla klienta odpada wyłącznie
    w sprawie bez źródeł, i robi to węzeł odpowiedzi, a nie model."""
    with pytest.raises(ValidationError):
        Proposal(text="", internal_notes="Szukałem po komunikacie.")


@pytest.mark.parametrize(
    ("model", "arguments"),
    [
        (Proposal,      {"text": "1. Od kiedy?", "internal_notes": "", "sources": ["41002"]}),
        (ProposalNotes, {"internal_notes": "Szukałem po komunikacie.", "text": "Prosimy o…"}),
    ],
    ids=["źródła w propozycji", "treść w samych uwagach"],
)
def test_an_unknown_key_is_an_error(
    model:     type[Proposal] | type[ProposalNotes],
    arguments: dict[str, object],
) -> None:
    """Sprawdza, czy klucz spoza schematu daje błąd walidacji: w propozycji lista źródeł podana
    przez model, a w samych uwagach treść dla klienta.

    Wyłapuje źródła zadeklarowane przez model, które przeszłyby obok listy z odczytów (zasada 9),
    oraz same uwagi, które po cichu przyjęłyby treść dla klienta."""
    with pytest.raises(ValidationError):
        model.model_validate(arguments)
