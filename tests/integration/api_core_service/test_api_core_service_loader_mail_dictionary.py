"""
Description:
Loader słownika maili (`core_service/loader_mail_dictionary.py`): słownik szablonów
i nazwy dostawcy ze zmyślonego katalogu `data/safe/mail/` oraz błędy konfiguracji przy pliku,
którego nie ma albo który ma zły kształt, na katalogach tymczasowych.
"""

from pathlib import Path

import pytest

from app.core_service.loader_mail_dictionary import (
    NAMES_FILE,
    TEMPLATES_FILE,
    MailDictionaryConfigError,
    load_mail_templates,
    load_vendor_names,
)
from tests._helpers.mail import SAFE_MAIL_DIR, VENDOR_NAME


def test_the_safe_dictionary_loads() -> None:
    """Sprawdza, czy słownik zmyślony z repo daje się wczytać: szablony z długością ciągu
    12 słów i co najmniej jednym skrótem oraz nazwę dostawcy.

    Wyłapuje słownik w repo w kształcie, którego loader nie przyjmuje (np. po zmianie modelu
    bez przebudowy słownika): wszystkie testy normalizera padłyby na wczytaniu."""
    templates = load_mail_templates(SAFE_MAIL_DIR)

    assert (templates.run_words, bool(templates.digests)) == (12, True)
    assert load_vendor_names(SAFE_MAIL_DIR).names == [VENDOR_NAME]


@pytest.mark.parametrize(
    ("file_name", "load"),
    [(TEMPLATES_FILE, load_mail_templates), (NAMES_FILE, load_vendor_names)],
    ids=["słownik", "nazwy"],
)
def test_a_missing_file_is_a_configuration_error(tmp_path: Path, file_name: str, load) -> None:
    """Sprawdza, czy brak pliku słownika albo nazw w katalogu kończy się błędem konfiguracji,
    który nazywa brakujący plik.

    Wyłapuje loader, który zamienia brak pliku na pusty słownik: wątki mailowe szłyby do
    anonimizatora bez czyszczenia i nikt by tego nie zauważył."""
    with pytest.raises(MailDictionaryConfigError, match=file_name):
        load(tmp_path)


@pytest.mark.parametrize(
    ("file_name", "content", "load"),
    [
        (TEMPLATES_FILE, "nie JSON", load_mail_templates),
        (TEMPLATES_FILE, '{"digests": []}', load_mail_templates),
        (NAMES_FILE, '{"names": []}', load_vendor_names),
        (NAMES_FILE, '{"names": ["Przykładsoft"], "uwagi": "x"}', load_vendor_names),
        (NAMES_FILE, '{"names": [" - "]}', load_vendor_names),
    ],
    ids=["zły JSON", "słownik bez pól", "pusta lista nazw", "pole spoza modelu", "nazwa bez słów"],
)
def test_a_file_in_a_wrong_shape_is_a_configuration_error(
    tmp_path:  Path,
    file_name: str,
    content:   str,
    load,
) -> None:
    """Sprawdza, czy plik, który nie jest JSON-em, nie ma pól słownika, ma pustą listę nazw,
    pole spoza modelu albo nazwę bez słów, kończy się błędem konfiguracji.

    Wyłapuje plik przyjęty mimo złego kształtu. Najgroźniejsza jest nazwa bez słów: pasuje do
    każdej wiadomości, więc każdą zrobiłaby wiadomością dostawcy."""
    (tmp_path / file_name).write_text(content, encoding="utf-8")

    with pytest.raises(MailDictionaryConfigError, match=file_name):
        load(tmp_path)
