import pytest
from pydantic import ValidationError

from app.config import Settings

# Limity wywołań narzędzi agenta w konfiguracji: pole na narzędzie i mapa, którą dostają węzeł
# `run_tools` i opisy narzędzi dla modelu.

LIMIT_FIELDS = [
    name for name in Settings.model_fields if name.startswith(Settings.TOOL_CALL_LIMIT_PREFIX)
]


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Description:
    Usuwa zmienne z limitami, żeby wartość wyeksportowana w powłoce nie wpłynęła na asercje.
    `.env` jest wyłączane per instancja przez `_env_file=None`.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        None — w środowisku procesu nie ma zmiennych `AGENT_MAX_CALLS_*`
    """
    for name in LIMIT_FIELDS:
        monkeypatch.delenv(name.upper(), raising=False)


def test_limits_are_a_map_from_tool_name_to_limit(clean_env: None) -> None:
    """Pola `agent_max_calls_<narzędzie>` → mapa nazwa narzędzia → limit, bez przedrostka."""
    limits = Settings(_env_file=None).tool_call_limits()

    assert limits["find_tickets_vector"] == 3
    assert limits["read_tickets_thread"] == 2
    assert limits["list_docs"]           == 1
    assert set(limits) == {name.removeprefix("agent_max_calls_") for name in LIMIT_FIELDS}


def test_a_limit_comes_from_the_environment(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AGENT_MAX_CALLS_READ_DOCS=5` → limit `read_docs` równy 5: wdrożenie stroi limity bez
    zmiany kodu."""
    monkeypatch.setenv("AGENT_MAX_CALLS_READ_DOCS", "5")

    assert Settings(_env_file=None).tool_call_limits()["read_docs"] == 5


def test_default_limits_are_cautious(clean_env: None) -> None:
    """Wartości domyślne → małe: limit ma chronić przed pętlą zużywającą tokeny, więc zaczyna
    ostrożnie, a podnosi go wdrożenie. Odczyt oddaje tysiące tokenów, więc ma najwyżej 3;
    wyszukiwanie kilkadziesiąt, a tekstowe bierze jedną frazę na wywołanie, więc najwyżej 5."""
    limits = Settings(_env_file=None).tool_call_limits()
    reads  = [limit for name, limit in limits.items() if name.startswith("read_")]

    assert all(1 <= limit <= 5 for limit in limits.values())
    assert all(limit <= 3 for limit in reads)


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_limit_below_one_is_refused(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
    value:       str,
) -> None:
    """Limit zerowy albo ujemny → błąd konfiguracji przy starcie: narzędzie, którego nie wolno
    wywołać ani razu, powinno zniknąć z grafu, a nie odmawiać przy pierwszym użyciu."""
    monkeypatch.setenv("AGENT_MAX_CALLS_LIST_DOCS", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
