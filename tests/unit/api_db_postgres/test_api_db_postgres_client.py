import asyncpg
import pytest

from app.db_postgres import DbPostgresConfigError, DbPostgresError, PostgresClient

# Klient testowany bez bazy: `asyncpg.create_pool` jest podmieniony, więc sprawdzamy to, co należy
# do NAS — odmowę złej konfiguracji i tłumaczenie błędów sterownika. Że Postgres naprawdę tak
# odpowiada, sprawdza test na stacku.


class StubPool:
    """
    Description:
    Pula połączeń bez bazy: na każde wywołanie odpowiada ustaloną wartością albo ustalonym
    wyjątkiem.
    """

    def __init__(
        self,
        answer: object = 1,               # np. [{"item_id": "90011"}]
        error:  Exception | None = None,  # np. asyncpg.PostgresError("…")
    ):
        """
        Description:
        Ustala odpowiedź puli.

        Example args:
            answer=1
            error=None

        Example result:
            StubPool odpowiadająca 1 na każde wywołanie
        """
        self._answer = answer
        self._error  = error

        self.closed = False

    async def _reply(self, *_: object) -> object:
        """
        Description:
        Oddaje ustaloną odpowiedź albo zgłasza ustalony wyjątek — wspólne dla wszystkich metod.

        Example args:
            (dowolne)

        Example result:
            1
        """
        if self._error is not None:
            raise self._error

        return self._answer

    fetchval = fetch = execute = _reply

    async def close(self) -> None:
        """
        Description:
        Zapamiętuje, że pulę zamknięto.

        Example args:
            (brak)

        Example result:
            None
        """
        self.closed = True


def make_client(
    **overrides: object,  # np. password=None
) -> PostgresClient:
    """
    Description:
    Buduje poprawnego klienta, żeby każdy test zmieniał tylko to, o co mu chodzi.

    Example args:
        overrides={"password": None}

    Example result:
        PostgresClient dla postgres:5432/helpdesk
    """
    arguments = {
        "host":     "postgres",
        "port":     5432,
        "database": "helpdesk",
        "user":     "helpdesk",
        "password": "helpdesk",
        **overrides,
    }

    return PostgresClient(**arguments)


def connect_to(
    monkeypatch: pytest.MonkeyPatch,
    outcome:     StubPool | Exception,  # pula, którą dostanie klient, albo błąd łączenia
) -> None:
    """
    Description:
    Podmienia zakładanie puli: klient dostaje podaną atrapę albo łączenie kończy się wyjątkiem.

    Example args:
        outcome=OSError("connection refused")

    Example result:
        None — kolejne `asyncpg.create_pool(...)` zgłosi ten wyjątek
    """
    async def create_pool(**_: object) -> StubPool:
        if isinstance(outcome, Exception):
            raise outcome

        return outcome

    monkeypatch.setattr(asyncpg, "create_pool", create_pool)


@pytest.mark.parametrize(
    ("argument", "value", "variable"),
    [
        ("password", None, "POSTGRES_PASSWORD"),
        ("password", "  ", "POSTGRES_PASSWORD"),
        ("host",     " ",  "POSTGRES_HOST"),
        ("database", "",   "POSTGRES_DB"),
        ("user",     "",   "POSTGRES_USER"),
    ],
)
def test_an_incomplete_configuration_is_refused_at_build_time(
    argument: str,
    value:    str | None,
    variable: str,
) -> None:
    """Brak hasła albo pusta część adresu → DbPostgresConfigError już przy budowie, z nazwą
    zmiennej."""
    with pytest.raises(DbPostgresConfigError, match=variable):
        make_client(**{argument: value})


@pytest.mark.parametrize(
    "error",
    [asyncpg.InvalidPasswordError("odrzucone"), asyncpg.InvalidCatalogNameError("brak bazy")],
    ids=["hasło odrzucone", "nie ma takiej bazy"],
)
async def test_a_rejected_configuration_is_a_config_error(
    monkeypatch: pytest.MonkeyPatch,
    error:       Exception,
) -> None:
    """Baza odrzuca hasło albo nie zna bazy → DbPostgresConfigError: czekanie tego nie naprawi."""
    connect_to(monkeypatch, error)

    with pytest.raises(DbPostgresConfigError):
        await make_client().fetch_value("SELECT 1")


@pytest.mark.parametrize(
    "error",
    [OSError("connection refused"), TimeoutError()],
    ids=["odmowa połączenia", "brak odpowiedzi w czasie"],
)
async def test_an_unreachable_database_is_a_db_error(
    monkeypatch: pytest.MonkeyPatch,
    error:       Exception,
) -> None:
    """Baza nieosiągalna → DbPostgresError, ale NIE DbPostgresConfigError: to awaria, którą
    ponowienie naprawi."""
    connect_to(monkeypatch, error)

    with pytest.raises(DbPostgresError) as caught:
        await make_client().fetch_value("SELECT 1")

    assert not isinstance(caught.value, DbPostgresConfigError)


@pytest.mark.parametrize("method", ["fetch_value", "fetch_rows", "execute"])
async def test_a_failed_query_is_a_db_error(monkeypatch: pytest.MonkeyPatch, method: str) -> None:
    """Baza odrzuca zapytanie → DbPostgresError z każdej metody, nigdy typ sterownika."""
    connect_to(monkeypatch, StubPool(error=asyncpg.PostgresError("syntax error")))

    with pytest.raises(DbPostgresError):
        await getattr(make_client(), method)("SELECT nonsens")


async def test_rows_come_back_as_plain_dicts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wiersze z bazy → zwykłe słowniki: typy sterownika nie wychodzą poza klienta."""
    connect_to(monkeypatch, StubPool(answer=[{"item_id": "90011", "total": 1}]))

    rows = await make_client().fetch_rows("SELECT …")

    assert rows == [{"item_id": "90011", "total": 1}]
    assert type(rows[0]) is dict


async def test_the_pool_is_closed_on_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zapytanie i zamknięcie → pula zamknięta; klient bez połączenia zamyka się bez błędu."""
    pool = StubPool()
    connect_to(monkeypatch, pool)
    client = make_client()

    await client.fetch_value("SELECT 1")
    await client.aclose()

    assert pool.closed is True
    assert await make_client().aclose() is None
