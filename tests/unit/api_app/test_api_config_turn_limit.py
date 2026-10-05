import pytest
from pydantic import ValidationError

from app.config import Settings

# Limit tur modelu w konfiguracji: jedna liczba na przebieg grafu z narzędziami, obok limitów
# wywołań poszczególnych narzędzi.


def test_the_turn_limit_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy limit tur modelu da się ustawić zmienną środowiskową: przy
    `AGENT_MAX_ITERATIONS=7` limit wynosi 7.

    Wyłapuje limit zaszyty w kodzie albo czytany spod innej nazwy: wdrożenie nie mogłoby go
    stroić bez zmiany kodu."""
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "7")

    assert Settings(_env_file=None).agent_max_iterations == 7


def test_the_turn_limit_is_not_a_tool_call_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sprawdza, czy limit tur modelu nie trafia do mapy limitów wywołań narzędzi: w mapie nie ma
    wpisu o nazwie `iterations`.

    Wyłapuje nazwanie pola limitu tur tak, że mapa wzięłaby je za limit narzędzia: mapa idzie
    do opisów narzędzi dla modelu, a narzędzia o nazwie `iterations` nie ma."""
    monkeypatch.delenv("AGENT_MAX_ITERATIONS", raising=False)

    assert "iterations" not in Settings(_env_file=None).tool_call_limits()


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_turn_limit_below_one_is_refused(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Sprawdza, czy limit tur modelu równy zero albo ujemny (`AGENT_MAX_ITERATIONS` równe 0 albo
    -1) daje błąd konfiguracji już przy jej wczytaniu.

    Wyłapuje przyjęcie takiego limitu: model nie dostałby ani jednej tury, więc żaden graf
    z narzędziami nie mógłby odpowiedzieć."""
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
