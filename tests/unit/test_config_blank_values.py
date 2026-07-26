import pytest

from app.config import Settings


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Description:
    Removes the variables these tests set, so a value exported in the developer's shell cannot
    leak into the assertions. `.env` is disabled per-instance via `_env_file=None`.

    Example args:
        (injected by pytest)

    Example result:
        None — the process environment no longer holds the tested keys
    """
    for name in ("QDRANT_URL", "LLM_MODEL", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)


def test_blank_string_falls_back_to_default(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty QDRANT_URL (what compose substitutes for an undefined var) → declared default."""
    monkeypatch.setenv("QDRANT_URL", "")

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == "http://qdrant:6333"


def test_whitespace_only_string_falls_back_to_default(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QDRANT_URL set to spaces → treated as absent, not as a valid address."""
    monkeypatch.setenv("QDRANT_URL", "   ")

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == "http://qdrant:6333"


def test_blank_optional_stays_none(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty LLM_MODEL → None, so the LLM factory can fail fast instead of sending model=''."""
    monkeypatch.setenv("LLM_MODEL", "")

    settings = Settings(_env_file=None)

    assert settings.llm_model is None


def test_real_value_survives(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-blank value → used verbatim (the blank filter must not swallow real configuration)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "openai"
