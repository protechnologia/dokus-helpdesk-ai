import logging

import pytest

from anonymizer_app.core_engine import FAKE_ENGINE_NAME, FakeEngine
from tests._helpers.anonymization import FAKE_ENGINE, RAW_TEXT, SENSITIVE


async def test_the_fake_returns_the_text_unchanged() -> None:
    """Sprawdza, czy atrapa silnika oddaje tekst bez żadnej zmiany.

    Wyłapuje atrapę, która coś w tekście zmienia: testy okablowania polegają na tym, że tekst
    przechodzi nietknięty, a każda zmiana wyglądałaby jak anonimizacja, której nie ma."""
    assert await FakeEngine().anonymize(RAW_TEXT) == RAW_TEXT


def test_the_fake_is_named_as_the_api_expects() -> None:
    """Sprawdza, czy atrapa silnika przedstawia się nazwą „fake", tą samą, po której klient
    w `api` rozpoznaje atrapę i odmawia jej wyniku.

    Wyłapuje zmianę nazwy po jednej stronie kontraktu: klient przestałby rozpoznawać atrapę
    i przepuściłby tekst bez anonimizacji do prawdziwego modelu."""
    assert FakeEngine().name == FAKE_ENGINE_NAME == FAKE_ENGINE


async def test_the_log_carries_lengths_only(caplog: pytest.LogCaptureFixture) -> None:
    """Sprawdza, czy wywołanie atrapy zapisuje w logu nazwę silnika i długości, a na żadnym
    poziomie, także DEBUG, nie zapisuje fragmentu danych osobowych z tekstu.

    Wyłapuje wpis w logu z treścią: ta usługa widzi surowe zgłoszenie, a logi nie są miejscem
    na dane klienta."""
    with caplog.at_level(logging.DEBUG):
        await FakeEngine().anonymize(RAW_TEXT)

    assert f"chars_in={len(RAW_TEXT)}" in caplog.text
    assert not [fragment for fragment in SENSITIVE if fragment in caplog.text]
