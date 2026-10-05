import pytest
from pydantic import ValidationError

from app.core_model.docs.doc_section import DocSection

VALID = {
    "section_id":  "adm-kancelaria-edoreczenia",
    "document":    "Instrukcja administratora",
    "version":     "4.12",
    "title":       "Uprawnienie do kancelarii e-Doręczeń",
    "description": "Kto i gdzie nadaje uprawnienie",
}


def test_a_top_level_section_needs_no_chapter_and_no_date() -> None:
    """Sprawdza, czy opis sekcji bez ścieżki rozdziału i bez daty wydania jest poprawny: ścieżka
    jest wtedy pustą listą, a data jest pusta (`None`).

    Wyłapuje model, który wymaga tych pól: sekcja bywa wprost w dokumencie, poza rozdziałami,
    a data wydania bywa nieznana, więc takich sekcji nie dałoby się opisać."""
    section = DocSection(**VALID)

    assert section.chapter_path == []
    assert section.date is None


@pytest.mark.parametrize("field", ["section_id", "document", "version", "title", "description"])
def test_an_empty_required_field_is_refused(field: str) -> None:
    """Sprawdza, czy pusta wartość w każdym z pól wymaganych opisu sekcji — identyfikatorze,
    dokumencie, wydaniu, tytule i opisie — daje błąd walidacji.

    Wyłapuje opis sekcji przyjęty z pustym polem. Najgroźniejsze jest puste wydanie: instrukcji
    do nieznanej wersji nie da się odróżnić od nieaktualnej."""
    with pytest.raises(ValidationError):
        DocSection(**{**VALID, field: ""})


def test_an_unknown_field_is_refused() -> None:
    """Sprawdza, czy pole, którego opis sekcji nie przewiduje (tu `text` z treścią sekcji), daje
    błąd walidacji.

    Wyłapuje ciche pomijanie nadmiarowych pól: treść sekcji nie należy do jej opisu, więc
    podana tutaj zniknęłaby bez ostrzeżenia."""
    with pytest.raises(ValidationError):
        DocSection(**VALID, text="Uprawnienie nadaje administrator…")
