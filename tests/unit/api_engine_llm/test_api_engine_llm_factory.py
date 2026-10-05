import pytest

from app.config import LLMSettings, Settings
from app.engine_llm import FakeLLMClient, LLMConfigError, LLMError, get_llm_client
from app.engine_llm.client.claude import ClaudeLLMClient
from app.engine_llm.client.ollama import OllamaLLMClient
from app.engine_llm.client.openai import OpenAILLMClient


def _settings(provider: str, **overrides) -> LLMSettings:   # np. "fake"
    """
    Description:
    Komplet ustawień roli generującej z jawnie podanym dostawcą, zbudowany przez `Settings` bez
    pliku `.env` — żeby zmienna wyeksportowana w powłoce nie mogła przesunąć asercji (argument
    konstruktora wygrywa ze środowiskiem). Nadpisania podaje się krótkimi nazwami pól kompletu.

    Example args:
        provider="claude"
        overrides={"api_key": "sk-ant-test", "model": "claude-haiku-4-5"}

    Example result:
        LLMSettings(env_prefix="LLM_GENERATION_", provider="claude", api_key="sk-ant-test", …)
    """
    fields   = {f"llm_generation_{name}": value for name, value in overrides.items()}
    settings = Settings(llm_generation_provider=provider, _env_file=None, **fields)

    return settings.llm_generation()


def _claude_settings(**overrides) -> LLMSettings:
    """
    Description:
    Kompletna konfiguracja Claude'a, z nadpisaniami na wierzchu. Test usuwa wtedy dokładnie tę
    jedną wartość, o którą mu chodzi, zamiast powtarzać cały komplet.

    Example args:
        overrides={"model": None}

    Example result:
        LLMSettings(provider="claude", api_key="sk-ant-test", model=None, …)
    """
    values = {"api_key": "sk-ant-test", "model": "claude-haiku-4-5"}
    values.update(overrides)

    return _settings("claude", **values)


def _openai_settings(**overrides) -> LLMSettings:
    """
    Description:
    Kompletna konfiguracja OpenAI, z nadpisaniami na wierzchu. Test usuwa wtedy dokładnie tę
    jedną wartość, o którą mu chodzi, zamiast powtarzać cały komplet.

    Example args:
        overrides={"model": None}

    Example result:
        LLMSettings(provider="openai", api_key="sk-proj-test", model=None, …)
    """
    values = {"api_key": "sk-proj-test", "model": "gpt-5.4-mini"}
    values.update(overrides)

    return _settings("openai", **values)


def test_default_provider_builds_the_offline_fake() -> None:
    """Sprawdza, czy przy domyślnym ustawieniu `LLM_GENERATION_PROVIDER=fake` fabryka buduje
    atrapę modelu (`FakeLLMClient`).

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
    brakującą zmienną `LLM_GENERATION_API_KEY`.

    Wyłapuje klienta zbudowanego bez klucza: brak wyszedłby wtedy dopiero jako odmowa dostawcy
    w środku żądania, bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_GENERATION_API_KEY"):
        get_llm_client(_claude_settings(api_key=None))


def test_claude_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `claude` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_GENERATION_MODEL`.

    Wyłapuje klienta zbudowanego bez modelu: brak wyszedłby wtedy dopiero przy pierwszym wywołaniu,
    bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_GENERATION_MODEL"):
        get_llm_client(_claude_settings(model=None))


def test_claude_config_error_names_every_missing_value() -> None:
    """Sprawdza, czy przy braku klucza i modelu naraz jeden komunikat błędu wymienia obie zmienne:
    `LLM_GENERATION_API_KEY` i `LLM_GENERATION_MODEL`.

    Wyłapuje sprawdzanie, które zatrzymuje się na pierwszym braku: operator poprawiałby `.env` dwa
    razy, bo o drugiej zmiennej dowiedziałby się dopiero po kolejnym starcie."""
    with pytest.raises(LLMConfigError) as exc:
        get_llm_client(_claude_settings(api_key=None, model=None))

    assert "LLM_GENERATION_API_KEY" in str(exc.value)
    assert "LLM_GENERATION_MODEL"   in str(exc.value)


def test_claude_with_unpriced_model_fails_at_build_time() -> None:
    """Sprawdza, czy model Claude'a, którego nie ma w cenniku (`claude-nieistniejacy-9`), kończy się
    błędem konfiguracji już przy budowie klienta, a komunikat mówi o cenniku.

    Wyłapuje klienta, który startuje z modelem bez ceny: brak wyszedłby wtedy dopiero przy liczeniu
    kosztu, po wywołaniu, za które trzeba już zapłacić."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_claude_settings(model="claude-nieistniejacy-9"))


def test_openai_provider_builds_the_openai_client() -> None:
    """Sprawdza, czy dostawca `openai` z kluczem i modelem z cennika daje klienta OpenAI
    (`OpenAILLMClient`).

    Wyłapuje fabrykę, która pod tą nazwą dostawcy buduje innego klienta albo odrzuca kompletną
    konfigurację."""
    client = get_llm_client(_openai_settings())

    assert isinstance(client, OpenAILLMClient)


def test_openai_without_api_key_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `openai` bez klucza kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_GENERATION_API_KEY`.

    Wyłapuje klienta zbudowanego bez klucza: brak wyszedłby wtedy dopiero jako odmowa dostawcy
    w środku żądania, bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_GENERATION_API_KEY"):
        get_llm_client(_openai_settings(api_key=None))


def test_openai_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `openai` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_GENERATION_MODEL`.

    Wyłapuje klienta zbudowanego bez modelu: brak wyszedłby wtedy dopiero przy pierwszym wywołaniu,
    bez wskazania, co poprawić w `.env`."""
    with pytest.raises(LLMConfigError, match="LLM_GENERATION_MODEL"):
        get_llm_client(_openai_settings(model=None))


def test_openai_config_error_names_the_provider() -> None:
    """Sprawdza, czy błąd konfiguracji dostawcy `openai` (tu brak klucza) ma w komunikacie nazwę
    tego dostawcy.

    Wyłapuje komunikat, który mówi tylko, której zmiennej brakuje: ten sam tekst zgłasza więcej niż
    jeden dostawca, więc bez nazwy nie wiadomo, którą część `.env` poprawić."""
    # Komunikat jest wspólny dla obu dostawców, więc bez nazwy czytający nie wie, którą sekcję
    # `.env` poprawić.
    with pytest.raises(LLMConfigError, match="openai"):
        get_llm_client(_openai_settings(api_key=None))


def test_openai_with_unpriced_model_fails_at_build_time() -> None:
    """Sprawdza, czy model OpenAI, którego nie ma w cenniku (`gpt-nieistniejacy-9`), kończy się
    błędem konfiguracji już przy budowie klienta, a komunikat mówi o cenniku.

    Wyłapuje klienta, który startuje z modelem bez ceny: brak wyszedłby wtedy dopiero przy liczeniu
    kosztu, po wywołaniu, za które trzeba już zapłacić."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_openai_settings(model="gpt-nieistniejacy-9"))


def test_openai_accepts_a_compatible_endpoint() -> None:
    """Sprawdza, czy przy dostawcy `openai` z ustawionym `LLM_GENERATION_BASE_URL` klient kieruje
    żądania pod podany adres (`example.invalid`).

    Wyłapuje fabrykę, która nie przekazuje adresu klientowi: żądania szłyby wtedy do oficjalnego API
    zamiast pod skonfigurowany adres."""
    client = get_llm_client(_openai_settings(base_url="https://example.invalid/v1"))

    assert "example.invalid" in str(client._client.base_url)


def test_ollama_provider_builds_the_ollama_client() -> None:
    """Sprawdza, czy dostawca `ollama` z samą nazwą modelu daje klienta Ollamy (`OllamaLLMClient`).

    Wyłapuje fabrykę, która pod tą nazwą dostawcy buduje innego klienta albo żąda wartości, których
    lokalny serwer nie potrzebuje."""
    client = get_llm_client(_settings("ollama", model="bielik-4.5b-v3.0-instruct:Q8_0"))

    assert isinstance(client, OllamaLLMClient)


def test_ollama_without_model_fails_at_build_time() -> None:
    """Sprawdza, czy dostawca `ollama` bez nazwy modelu kończy się błędem konfiguracji, który nazywa
    brakującą zmienną `LLM_GENERATION_MODEL`.

    Wyłapuje fabrykę, która buduje klienta bez modelu albo sama jakiś zgaduje: dla tej wartości nie
    ma sensownej wartości domyślnej, a brak wyszedłby dopiero przy pierwszym wywołaniu."""
    with pytest.raises(LLMConfigError, match="LLM_GENERATION_MODEL"):
        get_llm_client(_settings("ollama"))


def test_ollama_does_not_require_an_api_key() -> None:
    """Sprawdza, czy dostawca `ollama` z pustym `LLM_GENERATION_API_KEY` nadal daje klienta Ollamy.

    Wyłapuje fabrykę, która żąda klucza od każdego dostawcy: lokalny serwer klucza nie sprawdza,
    więc taki wymóg blokowałby start bez powodu."""
    client = get_llm_client(
        _settings("ollama", model="bielik-4.5b-v3.0-instruct:Q8_0", api_key=None)
    )

    assert isinstance(client, OllamaLLMClient)


def test_ollama_uses_the_local_default_address() -> None:
    """Sprawdza, czy dostawca `ollama` bez ustawionego `LLM_GENERATION_BASE_URL` celuje
    w domyślny adres Ollamy, z portem 11434.

    Wyłapuje fabrykę, która przy pustym adresie nie podstawia domyślnego: klient łączyłby się wtedy
    nie tam, gdzie nasłuchuje Ollama, choć jej port jest stały."""
    client = get_llm_client(_settings("ollama", model="bielik:Q8_0"))

    assert "11434" in str(client._client.base_url)


def test_ollama_accepts_a_custom_address() -> None:
    """Sprawdza, czy ustawione `LLM_GENERATION_BASE_URL` (tu adres `192.168.1.10`) wygrywa
    z domyślnym adresem Ollamy.

    Wyłapuje fabrykę, która zawsze wpisuje adres domyślny: nie dałoby się wtedy użyć Ollamy stojącej
    na innej maszynie."""
    client = get_llm_client(
        _settings("ollama", model="bielik:Q8_0", base_url="http://192.168.1.10:11434/v1")
    )

    assert "192.168.1.10" in str(client._client.base_url)


def test_each_role_builds_its_client_from_its_own_settings() -> None:
    """Sprawdza, czy dwie role dają dwóch różnych klientów, każdego ze swojego kompletu ustawień:
    przy modelu generującym z OpenAI i anonimizującym z Ollamy fabryka buduje klienta OpenAI dla
    pierwszej roli i klienta Ollamy, celującego w jej własny adres, dla drugiej.

    Wyłapuje konfigurację, w której jedna rola bierze wartości drugiej: model anonimizujący widzi
    surowy tekst zgłoszeń, więc pomyłka wysłałaby go do dostawcy modelu generującego."""
    settings = Settings(
        llm_generation_provider    = "openai",
        llm_generation_api_key     = "sk-proj-test",
        llm_generation_model       = "gpt-5.4-mini",
        llm_anonymization_provider = "ollama",
        llm_anonymization_model    = "model-lokalny:tag",
        llm_anonymization_base_url = "http://192.168.1.10:11434/v1",
        _env_file                  = None,
    )

    generation    = get_llm_client(settings.llm_generation())
    anonymization = get_llm_client(settings.llm_anonymization())

    assert isinstance(generation, OpenAILLMClient)
    assert isinstance(anonymization, OllamaLLMClient)
    assert "192.168.1.10" in str(anonymization._client.base_url)


def test_both_roles_default_to_the_offline_fake() -> None:
    """Sprawdza, czy bez żadnej konfiguracji obie role, generująca i anonimizująca, dostają atrapę
    modelu.

    Wyłapuje wartość domyślną, która dla którejś roli wskazuje prawdziwego dostawcę: świeżo
    uruchomiona aplikacja i testy wysyłałyby wtedy dane poza maszynę."""
    settings = Settings(_env_file=None)

    assert isinstance(get_llm_client(settings.llm_generation()), FakeLLMClient)
    assert isinstance(get_llm_client(settings.llm_anonymization()), FakeLLMClient)


def test_a_config_error_names_the_variable_of_its_role() -> None:
    """Sprawdza, czy błąd konfiguracji roli anonimizującej (tu `openai` bez klucza) nazywa zmienną
    tej roli, `LLM_ANONYMIZATION_API_KEY`, a nie zmienną roli generującej.

    Wyłapuje komunikat wskazujący nie tę konfigurację: przy dwóch kompletach operator poprawiałby
    klucz modelu generującego, a błąd by nie znikał."""
    settings = Settings(
        llm_anonymization_provider = "openai",
        llm_anonymization_model    = "gpt-5.4-mini",
        _env_file                  = None,
    )

    with pytest.raises(LLMConfigError) as exc:
        get_llm_client(settings.llm_anonymization())

    assert "LLM_ANONYMIZATION_API_KEY" in str(exc.value)
    assert "LLM_GENERATION"            not in str(exc.value)
