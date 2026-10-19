import pytest

from anonymizer_app.config import Settings
from anonymizer_app.core_engine import AgentEngine, FakeEngine, build_engine
from anonymizer_app.core_errors.engine_config_error import EngineConfigError
from anonymizer_app.core_errors.engine_error import EngineError


@pytest.mark.parametrize("engine", ["fake", " Fake "])
def test_the_default_engine_is_the_fake(engine: str) -> None:
    """Sprawdza, czy domyślna konfiguracja i wartość `ANONYMIZATION_ENGINE` „fake", także wpisana
    jako „ Fake ", dają atrapę silnika.

    Wyłapuje usługę, która bez ustawienia nie wstaje albo czyta nazwę silnika zależnie od
    wielkości liter i spacji, które wpisał człowiek."""
    assert isinstance(build_engine(Settings()), FakeEngine)
    assert isinstance(build_engine(Settings(anonymization_engine=engine)), FakeEngine)


def test_an_unknown_engine_fails_at_build_time() -> None:
    """Sprawdza, czy nieznana nazwa silnika kończy budowę błędem konfiguracji
    `EngineConfigError`, który podaje błędną wartość i dostępne silniki.

    Wyłapuje usługę, która z literówką w nazwie silnika wstaje i pada dopiero przy pierwszym
    zgłoszeniu, albo komunikat, który nie mówi, co poprawić."""
    with pytest.raises(EngineConfigError) as caught:
        build_engine(Settings(anonymization_engine="ner"))

    assert "'ner'"  in str(caught.value)
    assert "fake"   in str(caught.value)
    assert "agent"  in str(caught.value)


def test_a_config_error_is_an_engine_error() -> None:
    """Sprawdza, czy błąd konfiguracji silnika jest odmianą ogólnego błędu silnika
    (`EngineError`).

    Wyłapuje rozdzielenie tych klas: handler usługi łapie `EngineError` i musi rozpoznać w nim
    błąd konfiguracji, żeby nie zamienić go na uprzejme 503."""
    assert issubclass(EngineConfigError, EngineError)


# Konfiguracja silnika `agent`, która przechodzi: adres i model, okno serwera domyślne.
AGENT_SETTINGS = {
    "anonymization_engine":       "agent",
    "llm_anonymization_base_url": "http://model:8000/v1",
    "llm_anonymization_model":    "test-model",
}


async def test_the_agent_engine_is_built_from_the_model_settings() -> None:
    """Sprawdza, czy `ANONYMIZATION_ENGINE=agent` z adresem i nazwą modelu daje silnik `agent`,
    także zapisany wielkimi literami ze spacjami, i że budowa nie łączy się z modelem.

    Wyłapuje fabrykę, która nie zna nowego silnika albo łączy się z serwerem modelu przy starcie:
    usługa nie wstałaby, gdy pod z GPU jest chwilowo wyłączony."""
    engine = build_engine(Settings(**{**AGENT_SETTINGS, "anonymization_engine": " Agent "}))

    assert isinstance(engine, AgentEngine)
    assert engine.name == "agent"

    await engine.aclose()


@pytest.mark.parametrize(
    ("missing", "variable"),
    [
        ("llm_anonymization_base_url", "LLM_ANONYMIZATION_BASE_URL"),
        ("llm_anonymization_model",    "LLM_ANONYMIZATION_MODEL"),
    ],
    ids=["bez-adresu", "bez-modelu"],
)
def test_the_agent_engine_needs_an_address_and_a_model(missing: str, variable: str) -> None:
    """Sprawdza, czy silnik `agent` bez adresu albo bez nazwy modelu kończy budowę błędem
    konfiguracji, który nazywa brakującą zmienną.

    Wyłapuje adres domyślny albo cichy start bez modelu: ten model widzi surowe zgłoszenia, więc
    dokąd idą, ktoś musi wpisać świadomie, a `.env` sprzed p. 19.5 wskazywał model komercyjny."""
    settings = Settings(**{**AGENT_SETTINGS, missing: None})

    with pytest.raises(EngineConfigError) as caught:
        build_engine(settings)

    assert variable in str(caught.value)


def test_a_window_too_small_for_the_prompt_fails_at_build_time() -> None:
    """Sprawdza, czy okno serwera mniejsze niż prompt z największą częścią tekstu i odpowiedzią
    (tu 8192 tokeny) kończy budowę błędem konfiguracji z nazwą zmiennej i liczbą potrzebnych
    tokenów, a okno domyślne (16384) przechodzi.

    Wyłapuje start na serwerze z za małym oknem: vLLM odrzuciłby długie zgłoszenie w trakcie
    pracy, a Ollama ucięłaby je bez błędu, więc model nie zobaczyłby końca wątku."""
    with pytest.raises(EngineConfigError) as caught:
        build_engine(Settings(**AGENT_SETTINGS, llm_anonymization_num_ctx=8192))

    assert "LLM_ANONYMIZATION_NUM_CTX=8192" in str(caught.value)
    assert isinstance(build_engine(Settings(**AGENT_SETTINGS)), AgentEngine)
