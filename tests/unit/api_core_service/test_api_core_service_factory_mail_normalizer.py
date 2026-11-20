"""
Description:
Fabryka czyszczenia wątków mailowych dla tras grafów (`core_service/factory_mail_normalizer.py`):
z jakiego katalogu słownika powstaje normalizer i że powstaje raz na proces.
"""

from pathlib import Path

import pytest

from app.core_service.factory_mail_normalizer import get_mail_normalizer, process_mail_normalizer


@pytest.fixture(autouse=True)
def fresh_process_normalizer():
    """
    Description:
    Czyści normalizer zapamiętany na proces przed testem i po nim, żeby test widział konfigurację
    ustawioną u siebie, a następne testy — swoją.

    Example args:
        (brak)

    Example result:
        None
    """
    process_mail_normalizer.cache_clear()
    yield
    process_mail_normalizer.cache_clear()


def test_the_normalizer_reads_the_configured_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy normalizer z zależności tras czyta słownik z katalogu `TICKETS_MAIL_DIR`
    i czy dwa wywołania oddają ten sam obiekt.

    Wyłapuje fabrykę, która bierze katalog skądinąd (np. z korpusu zgłoszeń) albo buduje
    normalizer przy każdym żądaniu: trasy czyściłyby wątki słownikiem, którego nikt nie
    zbudował, i czytałyby konfigurację przy każdym zgłoszeniu."""
    monkeypatch.setenv("TICKETS_MAIL_DIR", "/dane/maile")

    normalizer = get_mail_normalizer()

    assert normalizer._directory == Path("/dane/maile")
    assert get_mail_normalizer() is normalizer
