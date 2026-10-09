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
    """Sprawdza, czy z pól konfiguracji `agent_max_calls_<narzędzie>` powstaje mapa od nazwy
    narzędzia do limitu wywołań: nazwy są bez przedrostka, każde takie pole ma swój wpis,
    a wartości domyślne to między innymi 5 dla `find_tickets_vector`, 3 dla
    `read_tickets_thread` i 1 dla `list_docs`.

    Wyłapuje mapę, która gubi narzędzie albo zostawia przedrostek w nazwie: limitu takiego
    narzędzia nie znalazłby ani węzeł wykonujący narzędzia, ani opis narzędzia dla modelu."""
    limits = Settings(_env_file=None).tool_call_limits()

    assert limits["find_tickets_vector"] == 5
    assert limits["read_tickets_thread"] == 3
    assert limits["list_docs"]           == 1
    assert set(limits) == {name.removeprefix("agent_max_calls_") for name in LIMIT_FIELDS}


def test_a_limit_comes_from_the_environment(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy limit wywołań narzędzia da się ustawić zmienną środowiskową: przy
    `AGENT_MAX_CALLS_READ_DOCS=7` limit dla `read_docs` wynosi 7.

    Wyłapuje limit zaszyty w kodzie albo czytany spod innej nazwy: wdrożenie nie mogłoby stroić
    limitów bez zmiany kodu, a ustawiona zmienna niczego by nie zmieniała."""
    monkeypatch.setenv("AGENT_MAX_CALLS_READ_DOCS", "7")

    assert Settings(_env_file=None).tool_call_limits()["read_docs"] == 7


def test_default_limits_are_cautious(clean_env: None) -> None:
    """Sprawdza, czy domyślne limity wywołań narzędzi są małe: każdy mieści się między 1 a 5,
    odczyt wątków zgłoszeń i odczyt sekcji dokumentacji mają najwyżej 3, a dwa wyższe limity,
    szukanie w kodzie aplikacji i odczyt pliku kodu, wynoszą po 10.

    Wyłapuje podniesienie wartości domyślnych: limit chroni przed pętlą zużywającą tokeny, więc
    ma zaczynać ostrożnie, a podnosić go ma wdrożenie. Odczyt wątków i sekcji oddaje tysiące
    tokenów, dlatego ma niższy limit niż wyszukiwania i krótkie karty. Szukanie w kodzie ma
    wyższy, bo od komunikatu do miejsca, które go wywołuje, idzie się kilkoma szukaniami
    z rzędu, a odczyt pliku kodu, bo po każdym takim szukaniu model czyta otoczenie trafionej
    linii; każdy kolejny wyjątek ma być dopisany tu świadomie."""
    limits = Settings(_env_file=None).tool_call_limits()
    costly = [limits["read_tickets_thread"], limits["read_docs"]]
    higher = {"find_code_text", "read_code_file"}
    others = [limit for name, limit in limits.items() if name not in higher]

    assert all(1 <= limit <= 5 for limit in others)
    assert all(limit <= 3 for limit in costly)
    assert limits["find_code_text"] == 10
    assert limits["read_code_file"] == 10


@pytest.mark.parametrize("value", ["0", "-1"])
def test_a_limit_below_one_is_refused(
    clean_env:   None,
    monkeypatch: pytest.MonkeyPatch,
    value:       str,
) -> None:
    """Sprawdza, czy limit wywołań równy zero albo ujemny (tu `AGENT_MAX_CALLS_LIST_DOCS` równe 0
    albo -1) daje błąd konfiguracji już przy jej wczytaniu.

    Wyłapuje przyjęcie takiego limitu: narzędzie, którego nie wolno wywołać ani razu, powinno
    zniknąć z grafu, a nie odmawiać modelowi przy pierwszym użyciu."""
    monkeypatch.setenv("AGENT_MAX_CALLS_LIST_DOCS", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
