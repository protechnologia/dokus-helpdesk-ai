import pytest
from pydantic import ValidationError

from app.anonymization import AnonymizedText


def test_empty_anonymized_text_is_refused() -> None:
    """Pusty tekst po anonimizacji → ValidationError: anonimizator, który zwrócił nic, zawiódł,
    a pusta treść poszłaby do modelu jako „zgłoszenie"."""
    with pytest.raises(ValidationError):
        AnonymizedText(text="")
