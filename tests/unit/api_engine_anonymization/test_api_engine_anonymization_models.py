import pytest
from pydantic import ValidationError

from app.engine_anonymization import AnonymizedText


def test_empty_anonymized_text_is_refused() -> None:
    """Sprawdza, czy pusty tekst po anonimizacji daje błąd walidacji.

    Wyłapuje przyjęcie pustego wyniku: anonimizator, który nic nie zwrócił, zawiódł, a pusta
    treść poszłaby do modelu jako zgłoszenie."""
    with pytest.raises(ValidationError):
        AnonymizedText(text="")
