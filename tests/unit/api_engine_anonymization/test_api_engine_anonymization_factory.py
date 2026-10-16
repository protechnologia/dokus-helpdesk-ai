import pytest

from app.config import Settings
from app.engine_anonymization import AnonymizerClient, FakeAnonymizer, build_anonymizer


@pytest.mark.parametrize("provider", ["fake", " Fake "])
def test_the_fake_llm_gets_the_fake_anonymizer(provider: str) -> None:
    """Sprawdza, czy przy atrapie modelu generującego (`LLM_GENERATION_PROVIDER=fake`, także
    wpisanej jako „ Fake ") fabryka buduje atrapę anonimizatora.

    Wyłapuje fabrykę, która przy atrapie modelu buduje klienta usługi albo czyta wartość inaczej
    niż fabryka grafów: przy atrapie modelu nic nie wychodzi poza proces, więc aplikacja ma
    działać bez usługi `anonymizer`."""
    settings = Settings(llm_generation_provider=provider, _env_file=None)

    assert isinstance(build_anonymizer(settings), FakeAnonymizer)


def test_a_real_llm_gets_the_client_of_the_anonymizer_service() -> None:
    """Sprawdza, czy przy prawdziwym dostawcy modelu generującego (tu `openai`) fabryka buduje
    klienta usługi `anonymizer` z adresem i limitem czasu z konfiguracji
    (`ANONYMIZATION_BASE_URL`, `ANONYMIZATION_TIMEOUT_SECONDS`).

    Wyłapuje atrapę anonimizatora przy modelu zewnętrznym — surowe zgłoszenia wychodziłyby do
    dostawcy bez anonimizacji — oraz klienta, który gubi adres albo limit czasu z konfiguracji
    i rozmawia nie z tą usługą albo czeka dłużej, niż wolno."""
    settings = Settings(
        llm_generation_provider       = "openai",
        anonymization_base_url        = "http://anon:9000",
        anonymization_timeout_seconds = 7.5,
        _env_file                     = None,
    )

    anonymizer = build_anonymizer(settings)

    assert isinstance(anonymizer, AnonymizerClient)
    assert str(anonymizer._client.base_url) == "http://anon:9000"
    assert anonymizer._client.timeout.read  == 7.5


def test_the_anonymization_model_does_not_decide_about_the_anonymizer() -> None:
    """Sprawdza, czy o wyborze anonimizatora rozstrzyga wyłącznie model generujący: prawdziwy model
    anonimizujący przy atrapie modelu generującego daje atrapę anonimizatora, a atrapa modelu
    anonimizującego przy prawdziwym modelu generującym daje klienta usługi.

    Wyłapuje fabrykę, która czyta konfigurację nie tej roli: atrapa modelu anonimizującego
    przepuściłaby prawdziwy model generujący bez usługi `anonymizer`."""
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
    assert isinstance(build_anonymizer(real_writer), AnonymizerClient)


async def test_the_fake_passes_text_through_unchanged() -> None:
    """Sprawdza, czy atrapa anonimizatora oddaje podany tekst bez zmian, opakowany
    w `AnonymizedText`, i zapisuje go na swojej liście `texts`.

    Wyłapuje zmianę zachowania atrapy: testy polegają na tym, że tekst przechodzi nietknięty
    i że na liście widać, co przeszło przez anonimizację. To, że atrapa niczego nie anonimizuje,
    jest też powodem, dla którego fabryka buduje ją tylko przy atrapie modelu."""
    anonymizer = FakeAnonymizer()

    result = await anonymizer.anonymize("Jan Kowalski zgłasza błąd")

    assert result.text      == "Jan Kowalski zgłasza błąd"
    assert anonymizer.texts == ["Jan Kowalski zgłasza błąd"]
