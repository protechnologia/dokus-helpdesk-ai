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
    for name in ("QDRANT_URL", "LLM_GENERATION_MODEL", "LLM_GENERATION_PROVIDER"):
        monkeypatch.delenv(name, raising=False)


def test_blank_string_falls_back_to_default(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy pusta zmienna `QDRANT_URL` daje w konfiguracji adres domyślny
    `http://qdrant:6333`, a nie pusty adres.

    Wyłapuje brak filtra pustych wartości: `docker compose` wstawia pusty tekst za zmienną,
    której nikt nie ustawił, więc usługa dostałaby pusty adres i padłaby dopiero przy
    pierwszym połączeniu."""
    monkeypatch.setenv("QDRANT_URL", "")

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == "http://qdrant:6333"


def test_whitespace_only_string_falls_back_to_default(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zmienna `QDRANT_URL` złożona z samych spacji jest traktowana jak nieustawiona
    i daje adres domyślny `http://qdrant:6333`.

    Wyłapuje filtr, który odsiewa tylko dokładnie pusty tekst: adres ze spacji zostałby przyjęty
    jako poprawny i usługa próbowałaby się z nim łączyć."""
    monkeypatch.setenv("QDRANT_URL", "   ")

    settings = Settings(_env_file=None)

    assert settings.qdrant_url == "http://qdrant:6333"


def test_blank_optional_stays_none(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy pusta zmienna `LLM_GENERATION_MODEL` daje w konfiguracji brak wartości
    (`None`), a nie pusty tekst.

    Wyłapuje pusty tekst przyjęty jako nazwa modelu: budowa klienta modelu nie zgłosiłaby wtedy
    od razu braku nazwy, tylko wysłałaby do dostawcy żądanie z pustą nazwą modelu."""
    monkeypatch.setenv("LLM_GENERATION_MODEL", "")

    settings = Settings(_env_file=None)

    assert settings.llm_generation_model is None


def test_real_value_survives(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy zwykła, niepusta wartość (tu `LLM_GENERATION_PROVIDER=openai`) trafia do
    konfiguracji bez zmian.

    Wyłapuje zbyt gorliwy filtr pustych wartości, który wycinałby też prawdziwe ustawienia:
    usługa działałaby wtedy po cichu na wartościach domyślnych."""
    monkeypatch.setenv("LLM_GENERATION_PROVIDER", "openai")

    settings = Settings(_env_file=None)

    assert settings.llm_generation_provider == "openai"
