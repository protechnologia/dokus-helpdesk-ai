import pytest

from app.config import Settings
from app.llm import FakeLLMClient, LLMConfigError, LLMError, get_llm_client
from app.llm.client_claude import ClaudeLLMClient
from app.llm.client_openai import OpenAILLMClient


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
    """LLM_PROVIDER=fake (the shipped default) → FakeLLMClient, so nothing leaves the machine."""
    client = get_llm_client(_settings("fake"))

    assert isinstance(client, FakeLLMClient)


def test_provider_name_is_read_case_and_space_insensitively() -> None:
    """Provider typed as "  FAKE " in .env → same client; casing must not decide the provider."""
    client = get_llm_client(_settings("  FAKE "))

    assert isinstance(client, FakeLLMClient)


def test_unimplemented_provider_fails_at_build_time() -> None:
    """Provider this build has no client for → LLMConfigError at construction, not at request."""
    with pytest.raises(LLMConfigError):
        get_llm_client(_settings("openai"))


def test_config_error_names_the_offending_value() -> None:
    """Error message quotes the rejected value → the operator sees what to fix in .env."""
    with pytest.raises(LLMConfigError, match="bielik-runpod"):
        get_llm_client(_settings("bielik-runpod"))


def test_config_error_is_catchable_as_the_layer_error() -> None:
    """LLMConfigError is an LLMError → callers can catch one type for the whole LLM layer."""
    with pytest.raises(LLMError):
        get_llm_client(_settings("openai"))


def test_claude_provider_builds_the_claude_client() -> None:
    """LLM_PROVIDER=claude with key and model → ClaudeLLMClient, ready to call the API."""
    client = get_llm_client(_claude_settings())

    assert isinstance(client, ClaudeLLMClient)


def test_claude_without_api_key_fails_at_build_time() -> None:
    """Provider claude without LLM_API_KEY → LLMConfigError naming the missing key."""
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        get_llm_client(_claude_settings(llm_api_key=None))


def test_claude_without_model_fails_at_build_time() -> None:
    """Provider claude without LLM_MODEL → LLMConfigError naming the missing model."""
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        get_llm_client(_claude_settings(llm_model=None))


def test_claude_config_error_names_every_missing_value() -> None:
    """Both values absent → one error naming both, so .env is fixed in a single pass."""
    with pytest.raises(LLMConfigError) as exc:
        get_llm_client(_claude_settings(llm_api_key=None, llm_model=None))

    assert "LLM_API_KEY" in str(exc.value)
    assert "LLM_MODEL"   in str(exc.value)


def test_claude_with_unpriced_model_fails_at_build_time() -> None:
    """Model spoza cennika → LLMConfigError przy budowie, zanim przebieg cokolwiek kosztuje."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_claude_settings(llm_model="claude-nieistniejacy-9"))


def test_openai_provider_builds_the_openai_client() -> None:
    """LLM_PROVIDER=openai z kluczem i modelem → OpenAILLMClient gotowy do wywołania API."""
    client = get_llm_client(_openai_settings())

    assert isinstance(client, OpenAILLMClient)


def test_openai_without_api_key_fails_at_build_time() -> None:
    """Provider openai bez LLM_API_KEY → LLMConfigError nazywający brakujący klucz."""
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        get_llm_client(_openai_settings(llm_api_key=None))


def test_openai_without_model_fails_at_build_time() -> None:
    """Provider openai bez LLM_MODEL → LLMConfigError nazywający brakujący model."""
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        get_llm_client(_openai_settings(llm_model=None))


def test_openai_config_error_names_the_provider() -> None:
    """Błąd konfiguracji openai → nazwa dostawcy w komunikacie, nie samo 'brakuje wartości'."""
    # Komunikat jest wspólny dla obu dostawców, więc bez nazwy czytający nie wie, którą sekcję
    # `.env` poprawić.
    with pytest.raises(LLMConfigError, match="openai"):
        get_llm_client(_openai_settings(llm_api_key=None))


def test_openai_with_unpriced_model_fails_at_build_time() -> None:
    """Model spoza cennika → LLMConfigError przy budowie, zanim przebieg cokolwiek kosztuje."""
    with pytest.raises(LLMConfigError, match="cennik"):
        get_llm_client(_openai_settings(llm_model="gpt-nieistniejacy-9"))


def test_openai_accepts_a_compatible_endpoint() -> None:
    """LLM_BASE_URL ustawione → klient celuje w podany endpoint; tą drogą wejdzie Bielik."""
    client = get_llm_client(_openai_settings(llm_base_url="https://example.invalid/v1"))

    assert "example.invalid" in str(client._client.base_url)
