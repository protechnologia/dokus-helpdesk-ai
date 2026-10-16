import pytest

from app.config import Settings
from app.engine_anonymization import AnonymizerClient, FakeAnonymizer, build_anonymizer
from tests._helpers.anonymization import accepts_the_fake_engine

# Dostawca modelu generującego i to, czy klient ma przyjąć wynik atrapy silnika.
PROVIDERS = [
    pytest.param("fake", True, id="fake"),
    pytest.param(" Fake ", True, id="Fake ze spacjami"),
    pytest.param("openai", False, id="openai"),
    pytest.param("ollama", False, id="ollama"),
]


@pytest.mark.parametrize(("provider", "fake_engine_allowed"), PROVIDERS)
async def test_every_provider_gets_the_client_of_the_anonymizer_service(
    provider:            str,
    fake_engine_allowed: bool,
) -> None:
    """Sprawdza, czy przy każdym dostawcy modelu generującego fabryka buduje klienta usługi
    `anonymizer`, a ten przyjmuje wynik atrapy silnika tylko przy atrapie modelu (także wpisanej
    jako „ Fake "), a przy `openai` i `ollama` odmawia.

    Wyłapuje fabrykę, która przy atrapie modelu buduje własną atrapę anonimizatora zamiast pytać
    usługę, i taką, która daje zgodę na atrapę silnika przy prawdziwym modelu: surowe zgłoszenie
    poszłoby wtedy do modelu zewnętrznego. Wyłapuje też odczyt dostawcy inny niż w fabryce
    grafów, przy którym atrapa modelu kończyłaby każdą trasę błędem konfiguracji."""
    settings = Settings(llm_generation_provider=provider, _env_file=None)

    anonymizer = build_anonymizer(settings)

    assert isinstance(anonymizer, AnonymizerClient)
    assert await accepts_the_fake_engine(anonymizer) == fake_engine_allowed


def test_the_client_gets_the_address_and_timeout_from_the_config() -> None:
    """Sprawdza, czy klient usługi `anonymizer` z fabryki dostaje adres i limit czasu
    z konfiguracji (`ANONYMIZATION_BASE_URL`, `ANONYMIZATION_TIMEOUT_SECONDS`).

    Wyłapuje klienta, który gubi adres albo limit czasu z konfiguracji i rozmawia nie z tą
    usługą albo czeka dłużej, niż wolno."""
    settings = Settings(
        llm_generation_provider       = "openai",
        anonymization_base_url        = "http://anon:9000",
        anonymization_timeout_seconds = 7.5,
        _env_file                     = None,
    )

    anonymizer = build_anonymizer(settings)

    assert str(anonymizer._client.base_url) == "http://anon:9000"
    assert anonymizer._client.timeout.read  == 7.5


async def test_the_anonymization_model_does_not_decide_about_the_fake_engine() -> None:
    """Sprawdza, czy o zgodzie na atrapę silnika rozstrzyga wyłącznie model generujący: prawdziwy
    model anonimizujący przy atrapie modelu generującego daje klienta ze zgodą, a atrapa modelu
    anonimizującego przy prawdziwym modelu generującym — klienta bez zgody.

    Wyłapuje fabrykę, która czyta konfigurację nie tej roli: atrapa modelu anonimizującego
    przepuściłaby wynik atrapy silnika do prawdziwego modelu generującego."""
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

    assert await accepts_the_fake_engine(build_anonymizer(local_helper)) is True
    assert await accepts_the_fake_engine(build_anonymizer(real_writer)) is False


async def test_the_fake_passes_text_through_unchanged() -> None:
    """Sprawdza, czy atrapa anonimizatora oddaje podany tekst bez zmian, opakowany
    w `AnonymizedText`, i zapisuje go na swojej liście `texts`.

    Wyłapuje zmianę zachowania atrapy: testy polegają na tym, że tekst przechodzi nietknięty
    i że na liście widać, co przeszło przez anonimizację. To, że atrapa niczego nie anonimizuje,
    jest też powodem, dla którego aplikacja w czasie działania jej nie używa."""
    anonymizer = FakeAnonymizer()

    result = await anonymizer.anonymize("Jan Kowalski zgłasza błąd")

    assert result.text      == "Jan Kowalski zgłasza błąd"
    assert anonymizer.texts == ["Jan Kowalski zgłasza błąd"]
