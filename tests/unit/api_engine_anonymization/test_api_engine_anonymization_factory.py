import pytest

from app.config import Settings
from app.engine_anonymization import AnonymizationConfigError, FakeAnonymizer, build_anonymizer


def test_the_fake_llm_gets_the_fake_anonymizer() -> None:
    """Sprawdza, czy przy atrapie modelu generującego (`LLM_GENERATION_PROVIDER=fake`) fabryka
    buduje atrapę anonimizatora.

    Wyłapuje fabrykę, która odmawia także wtedy albo oddaje coś innego: przy atrapie modelu nic
    nie wychodzi poza proces, więc aplikacja ma się uruchamiać bez prawdziwego anonimizatora."""
    settings = Settings(llm_generation_provider="fake", _env_file=None)

    assert isinstance(build_anonymizer(settings), FakeAnonymizer)


def test_a_real_llm_without_a_real_anonymizer_refuses_to_start() -> None:
    """Sprawdza, czy przy prawdziwym dostawcy modelu generującego (tu
    `LLM_GENERATION_PROVIDER=openai`) fabryka anonimizatora kończy się błędem konfiguracji
    `AnonymizationConfigError`.

    Wyłapuje zbudowanie atrapy przy modelu zewnętrznym: atrapa przepuszcza tekst bez zmian, więc
    surowe zgłoszenia wychodziłyby do dostawcy bez anonimizacji."""
    settings = Settings(llm_generation_provider="openai", _env_file=None)

    with pytest.raises(AnonymizationConfigError):
        build_anonymizer(settings)


def test_the_anonymization_model_does_not_decide_about_the_guard() -> None:
    """Sprawdza, czy o odmowie rozstrzyga wyłącznie model generujący: prawdziwy model anonimizujący
    przy atrapie modelu generującego nie blokuje startu, a atrapa modelu anonimizującego nie
    znosi odmowy przy prawdziwym modelu generującym.

    Wyłapuje strażnika, który czyta konfigurację nie tej roli: skonfigurowanie lokalnego modelu
    do anonimizacji blokowałoby stack, a prawdziwy model generujący przeszedłby bez
    anonimizatora."""
    local_helper = Settings(
        llm_generation_provider    = "fake",
        llm_anonymization_provider = "ollama",
        _env_file                  = None,
    )
    real_writer = Settings(
        llm_generation_provider    = "openai",
        llm_anonymization_provider = "fake",
        _env_file                  = None,
    )

    assert isinstance(build_anonymizer(local_helper), FakeAnonymizer)

    with pytest.raises(AnonymizationConfigError):
        build_anonymizer(real_writer)


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
