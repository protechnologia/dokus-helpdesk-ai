import pytest
from pydantic import ValidationError

from app.core_model.doc_section import DocSection

VALID = {
    "section_id":  "adm-kancelaria-edoreczenia",
    "document":    "Instrukcja administratora",
    "version":     "4.12",
    "title":       "Uprawnienie do kancelarii e-Doręczeń",
    "description": "Kto i gdzie nadaje uprawnienie",
}


def test_a_top_level_section_needs_no_chapter_and_no_date() -> None:
    """Sekcja bez ścieżki rozdziału i bez daty → poprawna: stoi wprost w dokumencie, a data
    wydania bywa nieznana."""
    section = DocSection(**VALID)

    assert section.chapter_path == []
    assert section.date is None


@pytest.mark.parametrize("field", ["section_id", "document", "version", "title", "description"])
def test_an_empty_required_field_is_refused(field: str) -> None:
    """Puste pole wymagane → ValidationError; przy `version` dlatego, że instrukcja do nieznanego
    wydania jest nie do odróżnienia od nieaktualnej."""
    with pytest.raises(ValidationError):
        DocSection(**{**VALID, field: ""})


def test_an_unknown_field_is_refused() -> None:
    """Pole spoza kontraktu → ValidationError: treść sekcji nie należy do jej opisu."""
    with pytest.raises(ValidationError):
        DocSection(**VALID, text="Uprawnienie nadaje administrator…")
