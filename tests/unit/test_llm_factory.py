import pytest

from app.config import Settings
from app.llm import FakeLLMClient, LLMConfigError, LLMError, get_llm_client


def _settings(provider: str) -> Settings:   # e.g. "fake"
    """
    Description:
    Builds Settings with an explicit provider and no `.env`, so the assertions cannot be moved by
    a variable exported in the developer's shell (an init argument outranks the environment).

    Example args:
        provider="fake"

    Example result:
        Settings(llm_provider="fake", …)
    """
    return Settings(llm_provider=provider, _env_file=None)


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
