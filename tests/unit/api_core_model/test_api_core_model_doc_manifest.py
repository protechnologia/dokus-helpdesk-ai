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
    """Sprawdza, czy z poprawnego manifestu z dwiema sekcjami powstają dwa opisy sekcji w tej
    samej kolejności, a pierwszy niesie tytuł dokumentu, wydanie i datę z nagłówka manifestu oraz
    własną ścieżkę rozdziału.

    Wyłapuje opis sekcji, który gubi dokument albo wydanie: stoją one w manifeście tylko raz,
    w nagłówku, więc bez przepisania nie byłoby widać, z której instrukcji i wersji sekcja
    pochodzi."""
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
    """Sprawdza, czy manifest bez daty wydania jest poprawny, a data w manifeście i w opisie
    pierwszej sekcji jest wtedy pusta (`None`).

    Wyłapuje model, który wymaga daty: data wydania bywa nieznana, inaczej niż samo wydanie,
    więc dokumentu bez daty nie dałoby się wgrać."""
    manifest = DocManifest(**{key: value for key, value in VALID.items() if key != "date"})

    assert manifest.date is None
    assert manifest.to_sections()[0].date is None


def test_synthetic_has_no_default() -> None:
    """Sprawdza, czy manifest bez pola `synthetic` jest odrzucany błędem walidacji, który nazywa
    to pole.

    Wyłapuje dodanie wartości domyślnej: od tej flagi zależy, do którego indeksu dokument wolno
    wgrać, więc wartość zgadnięta za autora mogłaby skierować go do niewłaściwego indeksu."""
    with pytest.raises(ValidationError, match="synthetic"):
        DocManifest(**{key: value for key, value in VALID.items() if key != "synthetic"})


@pytest.mark.parametrize("value", ["true", "nie", 1, None])
def test_synthetic_must_be_a_boolean(value: object) -> None:
    """Sprawdza, czy `synthetic` podane inaczej niż jako prawda albo fałsz — tekstem `true` lub
    `nie`, liczbą 1 albo jako wartość pusta — daje błąd walidacji z nazwą tego pola.

    Wyłapuje model, który sam zamienia tekst albo liczbę na prawdę lub fałsz: znaczenie flagi
    byłoby wtedy zgadywane, a od niej zależy, do którego indeksu dokument trafi."""
    with pytest.raises(ValidationError, match="synthetic"):
        DocManifest(**{**VALID, "synthetic": value})


@pytest.mark.parametrize("field", ["document", "version"])
def test_an_empty_header_field_is_refused(field: str) -> None:
    """Sprawdza, czy pusty tytuł dokumentu (`document`) albo puste wydanie (`version`) daje błąd
    walidacji z nazwą tego pola.

    Wyłapuje manifest przyjęty bez tytułu albo wydania: sekcje takiego dokumentu trafiłyby do
    indeksu bez informacji, z której instrukcji i z której wersji pochodzą."""
    with pytest.raises(ValidationError, match=field):
        DocManifest(**{**VALID, field: ""})


def test_a_manifest_without_sections_is_refused() -> None:
    """Sprawdza, czy manifest z pustą listą sekcji daje błąd walidacji z nazwą pola `sections`.

    Wyłapuje manifest przyjęty bez sekcji: taki dokument nie ma czego wgrać, więc wyglądałby na
    wczytany poprawnie, a do indeksu nie trafiłoby nic."""
    with pytest.raises(ValidationError, match="sections"):
        DocManifest(**{**VALID, "sections": []})


def test_an_unknown_header_key_is_refused() -> None:
    """Sprawdza, czy klucz, którego nagłówek manifestu nie przewiduje (tu `author`), daje błąd
    walidacji z nazwą tego klucza.

    Wyłapuje ciche pomijanie nieznanych kluczy: literówka w nazwie pola albo dopisana
    informacja zniknęłaby bez śladu i nikt by się o tym nie dowiedział."""
    with pytest.raises(ValidationError, match="author"):
        DocManifest(**VALID, author="Jan Kowalski")


def test_an_unknown_section_key_is_refused() -> None:
    """Sprawdza, czy klucz, którego wpis sekcji nie przewiduje (tu `body` z treścią sekcji), daje
    błąd walidacji z nazwą tego klucza.

    Wyłapuje ciche pomijanie nadmiarowych kluczy we wpisie sekcji: treść sekcji leży w osobnym
    pliku, więc treść wpisana do manifestu zniknęłaby bez ostrzeżenia."""
    with pytest.raises(ValidationError, match="body"):
        DocManifest(**{**VALID, "sections": [{**SECTION, "body": "Uprawnienie nadaje…"}]})


def test_a_repeated_section_id_is_refused() -> None:
    """Sprawdza, czy manifest, w którym ten sam identyfikator sekcji stoi dwa razy, daje błąd
    walidacji podający ten identyfikator.

    Wyłapuje przyjęcie powtórzonego identyfikatora: obie sekcje wskazywałyby jeden plik
    z treścią, więc jedna z nich po cichu zastąpiłaby drugą."""
    with pytest.raises(ValidationError, match="adm-kancelaria-edoreczenia"):
        DocManifest(**{**VALID, "sections": [SECTION, SECTION]})


@pytest.mark.parametrize("section_id", ["", "../poza", "adm/sekcja", "adm sekcja", ".md"])
def test_a_section_id_that_is_not_a_file_name_is_refused(section_id: str) -> None:
    """Sprawdza, czy identyfikator sekcji, który nie nadaje się na nazwę pliku — pusty,
    z ukośnikiem, ze spacją albo zaczynający się od kropki — daje błąd walidacji z nazwą pola
    `section_id`.

    Wyłapuje poluzowanie wzorca identyfikatora: jest on też nazwą pliku z treścią sekcji, więc
    wartość taka jak `../poza` wskazałaby plik poza katalogiem dokumentu."""
    with pytest.raises(ValidationError, match="section_id"):
        DocManifest(**{**VALID, "sections": [{**SECTION, "section_id": section_id}]})


@pytest.mark.parametrize("section_id", ["adm-kancelaria-epuap", "usr_odswiez", "4.12-zmiany", "A1"])
def test_a_plain_section_id_is_accepted(section_id: str) -> None:
    """Sprawdza, czy identyfikator sekcji złożony z liter, cyfr, łącznika, podkreślenia i kropki
    (na przykład `usr_odswiez` albo `4.12-zmiany`) jest przyjmowany i zapisany bez zmian.

    Wyłapuje zbyt ostry wzorzec identyfikatora, który odrzucałby zwykłe nazwy sekcji i nie
    pozwalał wgrać poprawnej dokumentacji."""
    manifest = DocManifest(**{**VALID, "sections": [{**SECTION, "section_id": section_id}]})

    assert manifest.sections[0].section_id == section_id
