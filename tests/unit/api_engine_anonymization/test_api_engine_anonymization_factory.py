import pytest

from app.config import Settings
from app.engine_anonymization import AnonymizationConfigError, FakeAnonymizer, build_anonymizer


def test_the_fake_llm_gets_the_fake_anonymizer() -> None:
    """Sprawdza, czy przy atrapie modelu (`LLM_PROVIDER=fake`) fabryka buduje atrapę
    anonimizatora.

    Wyłapuje fabrykę, która odmawia także wtedy albo oddaje coś innego: przy atrapie modelu nic
    nie wychodzi poza proces, więc aplikacja ma się uruchamiać bez prawdziwego anonimizatora."""
    settings = Settings(llm_provider="fake", _env_file=None)

    assert isinstance(build_anonymizer(settings), FakeAnonymizer)


def test_a_real_llm_without_a_real_anonymizer_refuses_to_start() -> None:
    """Sprawdza, czy przy prawdziwym dostawcy modelu (tu `LLM_PROVIDER=openai`) fabryka
    anonimizatora kończy się błędem konfiguracji `AnonymizationConfigError`.

    Wyłapuje zbudowanie atrapy przy modelu zewnętrznym: atrapa przepuszcza tekst bez zmian, więc
    surowe zgłoszenia wychodziłyby do dostawcy bez anonimizacji."""
    settings = Settings(llm_provider="openai", _env_file=None)

    with pytest.raises(AnonymizationConfigError):
        build_anonymizer(settings)


async def test_the_fake_passes_text_through_unchanged() -> None:
    """Sprawdza, czy atrapa anonimizatora oddaje podany tekst bez zmian, opakowany
    w `AnonymizedText`, i zapisuje go na swojej liście `texts`.

    Wyłapuje zmianę zachowania atrapy: testy polegają na tym, że tekst przechodzi nietknięty
    i że na liście widać, co przeszło przez anonimizację. To, że atrapa niczego nie anonimizuje,
    jest też powodem, dla którego fabryka nie dopuszcza jej do prawdziwego modelu."""
    anonymizer = FakeAnonymizer()

    result = await anonymizer.anonymize("Jan Kowalski zgłasza błąd")

    assert result.text      == "Jan Kowalski zgłasza błąd"
    assert anonymizer.texts == ["Jan Kowalski zgłasza błąd"]
