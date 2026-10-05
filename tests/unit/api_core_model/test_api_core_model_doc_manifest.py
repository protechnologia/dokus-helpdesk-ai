from datetime import date

import pytest
from pydantic import ValidationError

from app.core_model.docs.doc_manifest import DocManifest

SECTION = {
    "section_id":   "adm-kancelaria-edoreczenia",
    "chapter_path": ["Uprawnienia", "Kancelaria"],
    "title":        "Uprawnienie do kancelarii e-Doręczeń",
    "description":  "Kto i gdzie nadaje uprawnienie",
}

VALID = {
    "document":  "Instrukcja administratora",
    "version":   "4.12",
    "date":      "2026-05-04",
    "synthetic": False,
    "sections":  [SECTION, {**SECTION, "section_id": "adm-kancelaria-epuap"}],
}


def test_sections_carry_the_document_and_its_edition() -> None:
    """Poprawny manifest → opisy sekcji w kolejności manifestu, każdy z dokumentem, wydaniem
    i datą z nagłówka."""
    sections = DocManifest(**VALID).to_sections()

    assert [section.section_id for section in sections] == [
        "adm-kancelaria-edoreczenia",
        "adm-kancelaria-epuap",
    ]
    assert sections[0].document     == "Instrukcja administratora"
    assert sections[0].version      == "4.12"
    assert sections[0].date         == date(2026, 5, 4)
    assert sections[0].chapter_path == ["Uprawnienia", "Kancelaria"]


def test_the_date_is_optional() -> None:
    """Manifest bez daty wydania → poprawny: data bywa nieznana, wydanie nie."""
    manifest = DocManifest(**{key: value for key, value in VALID.items() if key != "date"})

    assert manifest.date is None
    assert manifest.to_sections()[0].date is None


def test_synthetic_has_no_default() -> None:
    """Manifest bez `synthetic` → ValidationError: od tej flagi zależy, do którego indeksu
    dokument wolno wgrać, więc nie zgadujemy jej."""
    with pytest.raises(ValidationError, match="synthetic"):
        DocManifest(**{key: value for key, value in VALID.items() if key != "synthetic"})


@pytest.mark.parametrize("value", ["true", "nie", 1, None])
def test_synthetic_must_be_a_boolean(value: object) -> None:
    """`synthetic` jako tekst albo liczba → ValidationError, bez domyślania się znaczenia."""
    with pytest.raises(ValidationError, match="synthetic"):
        DocManifest(**{**VALID, "synthetic": value})


@pytest.mark.parametrize("field", ["document", "version"])
def test_an_empty_header_field_is_refused(field: str) -> None:
    """Pusty tytuł dokumentu albo wydanie → ValidationError."""
    with pytest.raises(ValidationError, match=field):
        DocManifest(**{**VALID, field: ""})


def test_a_manifest_without_sections_is_refused() -> None:
    """Pusta lista sekcji → ValidationError: dokument bez sekcji nie ma czego wgrać."""
    with pytest.raises(ValidationError, match="sections"):
        DocManifest(**{**VALID, "sections": []})


def test_an_unknown_header_key_is_refused() -> None:
    """Klucz spoza kontraktu w nagłówku → ValidationError, nie ciche pominięcie."""
    with pytest.raises(ValidationError, match="author"):
        DocManifest(**VALID, author="Jan Kowalski")


def test_an_unknown_section_key_is_refused() -> None:
    """Klucz spoza kontraktu we wpisie sekcji → ValidationError: treść sekcji leży w pliku,
    nie w manifeście."""
    with pytest.raises(ValidationError, match="body"):
        DocManifest(**{**VALID, "sections": [{**SECTION, "body": "Uprawnienie nadaje…"}]})


def test_a_repeated_section_id_is_refused() -> None:
    """Ten sam `section_id` dwa razy → ValidationError nazywający identyfikator: obie sekcje
    wskazywałyby jeden plik."""
    with pytest.raises(ValidationError, match="adm-kancelaria-edoreczenia"):
        DocManifest(**{**VALID, "sections": [SECTION, SECTION]})


@pytest.mark.parametrize("section_id", ["", "../poza", "adm/sekcja", "adm sekcja", ".md"])
def test_a_section_id_that_is_not_a_file_name_is_refused(section_id: str) -> None:
    """Identyfikator z ukośnikiem, spacją albo od kropki → ValidationError: jest też nazwą pliku
    sekcji i nie może wyjść poza katalog dokumentu."""
    with pytest.raises(ValidationError, match="section_id"):
        DocManifest(**{**VALID, "sections": [{**SECTION, "section_id": section_id}]})


@pytest.mark.parametrize("section_id", ["adm-kancelaria-epuap", "usr_odswiez", "4.12-zmiany", "A1"])
def test_a_plain_section_id_is_accepted(section_id: str) -> None:
    """Litery, cyfry, łącznik, podkreślenie i kropka → poprawny identyfikator."""
    manifest = DocManifest(**{**VALID, "sections": [{**SECTION, "section_id": section_id}]})

    assert manifest.sections[0].section_id == section_id
