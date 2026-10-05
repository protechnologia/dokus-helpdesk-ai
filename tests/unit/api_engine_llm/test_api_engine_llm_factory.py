import pytest

from app.config import Settings
from app.engine_llm import FakeLLMClient, LLMConfigError, LLMError, get_llm_client
from app.engine_llm.client.claude import ClaudeLLMClient
from app.engine_llm.client.ollama import OllamaLLMClient
from app.engine_llm.client.openai import OpenAILLMClient


def _settings(provider: str, **overrides) -> Settings:   # e.g. "fake"
    """
    Description:
    Builds Settings with an explicit provider and no `.env`, so the assertions cannot be moved by
    a variable exported in the developer's shell (an init argument outranks the environment).

    Example args:
        provider="claude"
        overrides={"llm_api_key": "sk-ant-test", "llm_model": "claude-haiku-4-5"}

    Example result:
        Settings(llm_provider="claude", llm_api_key="sk-ant-test", …)
    """
    return Settings(llm_provider=provider, _env_file=None, **overrides)


def _claude_settings(**overrides) -> Settings:
    """
    Description:
    Builds a complete Claude configuration, with overrides applied on top. Each test then removes
    exactly the one value it is about, instead of restating the whole set.

    Example args:
        overrides={"llm_model": None}

    Example result:
        Settings(llm_provider="claude", llm_api_key="sk-ant-test", llm_model=None, …)
    """
    values = {"llm_api_key": "sk-ant-test", "llm_model": "claude-haiku-4-5"}
    values.update(overrides)

    return _settings("claude", **values)


def _openai_settings(**overrides) -> Settings:
    """
    Description:
    Builds a complete OpenAI configuration, with overrides applied on top. Each test then removes
    exactly the one value it is about, instead of restating the whole set.

    Example args:
        overrides={"llm_model": None}

    Example result:
        Settings(llm_provider="openai", llm_api_key="sk-proj-test", llm_model=None, …)
    """
    values = {"llm_api_key": "sk-proj-test", "llm_model": "gpt-5.4-mini"}
    values.update(overrides)

    return _settings("openai", **values)


def test_default_provider_builds_the_offline_fake() -> None:
    """Sprawdza, czy przy domyślnym ustawieniu `LLM_PROVIDER=fake` fabryka buduje atrapę modelu
    (`FakeLLMClient`).

    Wyłapuje fabrykę, która przy domyślnej konfiguracji buduje klienta prawdziwego dostawcy: świeżo
    uruchomiona aplikacja i testy wysyłałyby wtedy dane poza maszynę."""
    client = get_llm_client(_settings("fake"))

    assert isinstance(client, FakeLLMClient)


def test_provider_name_is_read_case_and_space_insensitively() -> None:
    """Sprawdza, czy nazwa dostawcy wpisana wielkimi literami i ze spacjami dookoła (`FAKE` zamiast
    `fake`) daje tego samego klienta.

    Wyłapuje porównywanie nazwy znak w znak: wartość wpisana ręcznie w `.env` z inną wielkością
    liter albo zbędną spacją kończyłaby się wtedy błędem o nieznanym dostawcy."""
    client = get_llm_client(_settings("  FAKE "))

    assert isinstance(client, FakeLLMClient)


def test_unimplemented_provider_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `openai` wybrany bez klucza i bez nazwy modelu kończy się wyjątkiem
    `LLMConfigError` już przy budowie klienta.

    Wyłapuje fabrykę, która buduje klienta mimo niepełnej konfiguracji: błąd wyszedłby wtedy dopiero
    w środku żądania, jako nieudane połączenie z dostawcą."""
    with pytest.raises(LLMConfigError):
        get_llm_client(_settings("openai"))


def test_config_error_names_the_offending_value() -> None:
    """Sprawdza, czy przy nieznanej nazwie dostawcy (`bielik-runpod`) komunikat błędu konfiguracji
    przytacza odrzuconą wartość.

    Wyłapuje komunikat, który mówi tylko, że dostawca jest nieznany: operator nie widziałby wtedy,
    którą wartość w `.env` ma poprawić."""
    with pytest.raises(LLMConfigError, match="bielik-runpod"):
        get_llm_client(_settings("bielik-runpod"))


def test_config_error_is_catchable_as_the_layer_error() -> None:
    """Sprawdza, czy błąd konfiguracji (`LLMConfigError`) da się złapać jako ogólny błąd warstwy
    modelu (`LLMError`); zgłasza go tu dostawca `openai` bez klucza i modelu.

    Wyłapuje rozdzielenie tych dwóch wyjątków: kod, który łapie jeden typ błędu dla całej warstwy
    modelu, przestałby wtedy widzieć błędy konfiguracji."""
    with pytest.raises(LLMError):
        get_llm_client(_settings("openai"))


def test_claude_provider_builds_the_claude_client() -> None:
    """Sprawdza, czy dostawca `claude` z kluczem i modelem z cennika daje klienta Claude'a
    (`ClaudeLLMClient`).

    Wyłapuje fabrykę, która pod tą nazwą dostawcy buduje innego klienta albo odrzuca kompletną
    konfigurację."""
    client = get_llm_client(_claude_settings())

    assert isinstance(client, ClaudeLLMClient)


def test_claude_without_api_key_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `claude` bez klucza kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_API_KEY`.

    Wyłapuje klienta zbudowanego bez klucza: brak wyszedłby wtedy dopiero jako odmowa dostawcy
    w środku żądania, bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        get_llm_client(_claude_settings(llm_api_key=None))


def test_claude_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `claude` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_MODEL`.

    Wyłapuje klienta zbudowanego bez modelu: brak wyszedłby wtedy dopiero przy pierwszym wywołaniu,
    bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        get_llm_client(_claude_settings(llm_model=None))


def test_claude_config_error_names_every_missing_value() -> None:
    """Sprawdza, czy przy braku klucza i modelu naraz jeden komunikat błędu wymienia obie zmienne:
    `LLM_API_KEY` i `LLM_MODEL`.

    Wyłapuje sprawdzanie, które zatrzymuje się na pierwszym braku: operator poprawiałby `.env` dwa
    razy, bo o drugiej zmiennej dowiedziałby się dopiero po kolejnym starcie."""
    with pytest.raises(LLMConfigError) as exc:
        get_llm_client(_claude_settings(llm_api_key=None, llm_model=None))

    assert "LLM_API_KEY" in str(exc.value)
    assert "LLM_MODEL"   in str(exc.value)


def test_claude_with_unpriced_model_fails_at_build_time() -> None:
    """Sprawdza, czy model Claude'a, którego nie ma w cenniku (`claude-nieistniejacy-9`), kończy się
    błędem konfiguracji już przy budowie klienta, a komunikat mówi o cenniku.

    Wyłapuje klienta, który startuje z modelem bez ceny: brak wyszedłby wtedy dopiero przy liczeniu
    kosztu, po wywołaniu, za które trzeba już zapłacić."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_claude_settings(llm_model="claude-nieistniejacy-9"))


def test_openai_provider_builds_the_openai_client() -> None:
    """Sprawdza, czy dostawca `openai` z kluczem i modelem z cennika daje klienta OpenAI
    (`OpenAILLMClient`).

    Wyłapuje fabrykę, która pod tą nazwą dostawcy buduje innego klienta albo odrzuca kompletną
    konfigurację."""
    client = get_llm_client(_openai_settings())

    assert isinstance(client, OpenAILLMClient)


def test_openai_without_api_key_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `openai` bez klucza kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_API_KEY`.

    Wyłapuje klienta zbudowanego bez klucza: brak wyszedłby wtedy dopiero jako odmowa dostawcy
    w środku żądania, bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        get_llm_client(_openai_settings(llm_api_key=None))


def test_openai_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `openai` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_MODEL`.

    Wyłapuje klienta zbudowanego bez modelu: brak wyszedłby wtedy dopiero przy pierwszym wywołaniu,
    bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        get_llm_client(_openai_settings(llm_model=None))


def test_openai_config_error_names_the_provider() -> None:
    """Sprawdza, czy błąd konfiguracji dostawcy `openai` (tu brak klucza) ma w komunikacie nazwę
    tego dostawcy.

    Wyłapuje komunikat, który mówi tylko, której zmiennej brakuje: ten sam tekst zgłasza więcej niż
    jeden dostawca, więc bez nazwy nie wiadomo, którą część `.env` poprawić."""
    # Komunikat jest wspólny dla obu dostawców, więc bez nazwy czytający nie wie, którą sekcję
    # `.env` poprawić.
    with pytest.raises(LLMConfigError, match="openai"):
        get_llm_client(_openai_settings(llm_api_key=None))


def test_openai_with_unpriced_model_fails_at_build_time() -> None:
    """Sprawdza, czy model OpenAI, którego nie ma w cenniku (`gpt-nieistniejacy-9`), kończy się
    błędem konfiguracji już przy budowie klienta, a komunikat mówi o cenniku.

    Wyłapuje klienta, który startuje z modelem bez ceny: brak wyszedłby wtedy dopiero przy liczeniu
    kosztu, po wywołaniu, za które trzeba już zapłacić."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_openai_settings(llm_model="gpt-nieistniejacy-9"))


def test_openai_accepts_a_compatible_endpoint() -> None:
    """Sprawdza, czy przy dostawcy `openai` z ustawionym `LLM_BASE_URL` klient kieruje żądania pod
    podany adres (`example.invalid`).

    Wyłapuje fabrykę, która nie przekazuje adresu klientowi: żądania szłyby wtedy do oficjalnego API
    zamiast pod skonfigurowany adres."""
    client = get_llm_client(_openai_settings(llm_base_url="https://example.invalid/v1"))

    assert "example.invalid" in str(client._client.base_url)


def test_ollama_provider_builds_the_ollama_client() -> None:
    """Sprawdza, czy dostawca `ollama` z samą nazwą modelu daje klienta Ollamy (`OllamaLLMClient`).

    Wyłapuje fabrykę, która pod tą nazwą dostawcy buduje innego klienta albo żąda wartości, których
    lokalny serwer nie potrzebuje."""
    client = get_llm_client(_settings("ollama", llm_model="bielik-4.5b-v3.0-instruct:Q8_0"))

    assert isinstance(client, OllamaLLMClient)


def test_ollama_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `ollama` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_MODEL`.

    Wyłapuje fabrykę, która buduje klienta bez modelu albo sama jakiś zgaduje: dla tej wartości nie
    ma sensownej wartości domyślnej, a brak wyszedłby dopiero przy pierwszym wywołaniu."""
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        get_llm_client(_settings("ollama"))


def test_ollama_does_not_require_an_api_key() -> None:
    """Sprawdza, czy dostawca `ollama` z pustym `LLM_API_KEY` nadal daje klienta Ollamy.

    Wyłapuje fabrykę, która żąda klucza od każdego dostawcy: lokalny serwer klucza nie sprawdza,
    więc taki wymóg blokowałby start bez powodu."""
    client = get_llm_client(
        _settings("ollama", llm_model="bielik-4.5b-v3.0-instruct:Q8_0", llm_api_key=None)
    )

    assert isinstance(client, OllamaLLMClient)


def test_ollama_uses_the_local_default_address() -> None:
    """Sprawdza, czy dostawca `ollama` bez ustawionego `LLM_BASE_URL` celuje w domyślny adres
    Ollamy, z portem 11434.

    Wyłapuje fabrykę, która przy pustym adresie nie podstawia domyślnego: klient łączyłby się wtedy
    nie tam, gdzie nasłuchuje Ollama, choć jej port jest stały."""
    client = get_llm_client(_settings("ollama", llm_model="bielik:Q8_0"))

    assert "11434" in str(client._client.base_url)


def test_ollama_accepts_a_custom_address() -> None:
    """Sprawdza, czy ustawione `LLM_BASE_URL` (tu adres `192.168.1.10`) wygrywa z domyślnym adresem
    Ollamy.

    Wyłapuje fabrykę, która zawsze wpisuje adres domyślny: nie dałoby się wtedy użyć Ollamy stojącej
    na innej maszynie."""
    client = get_llm_client(
        _settings("ollama", llm_model="bielik:Q8_0", llm_base_url="http://192.168.1.10:11434/v1")
    )

    assert "192.168.1.10" in str(client._client.base_url)
