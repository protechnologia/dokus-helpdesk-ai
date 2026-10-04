import asyncio
import logging

import asyncpg

from app.db_postgres.errors import DbPostgresConfigError, DbPostgresError

logger = logging.getLogger(__name__)

# Każde połączenie ładuje słownik przy pierwszym wyszukaniu (około 0,6 s i 32 MB), więc pula jest
# mała: kilka połączeń żyjących długo zamiast wielu krótkich.
POOL_MIN_SIZE = 1
POOL_MAX_SIZE = 4


class PostgresClient:
    """
    Description:
    Połączenie `api` z usługą `postgres` i nic więcej: pula, wykonanie zapytania, tłumaczenie
    błędów. „Klient" znaczy przekroczenie granicy procesu (CLAUDE.md -> „Warstwy kodu") — każda
    awaria tej rozmowy kończy się tutaj i staje się `DbPostgresError`, a sterownik jest importowany
    wyłącznie w tym pliku.

    Do czego:
    Warstwa niskopoziomowa pakietu `app/db_postgres/`. Nie zna żadnej tabeli ani żadnego zapytania —
    dostaje gotowy SQL z wartościami i oddaje wynik. Zapytania składają klasy tabel z `table/`,
    i TYLKO one wołają metody klienta: kod spoza `app/db_postgres/` buduje klienta, podaje go tabeli
    i nigdy nie pyta bazy sam.

    Flow:
        1. Budowany raz z `Settings` (host, port, baza, użytkownik, hasło, timeout) i używany
           wielokrotnie; sam konstruktor z nikim się nie łączy.
        2. Pula połączeń powstaje przy pierwszym zapytaniu (`_get_pool()`).
        3. `fetch_value()`, `fetch_rows()` i `execute()` wykonują podany SQL.
        4. `aclose()` zamyka pulę.
    """

    def __init__(
        self,
        host:     str,           # np. "postgres"
        port:     int,           # np. 5432
        database: str,           # np. "helpdesk"
        user:     str,           # np. "helpdesk"
        password: str | None,    # np. "helpdesk"
        timeout:  float = 30.0,  # sekundy: łączenie i każde zapytanie
    ):
        """
        Description:
        Buduje klienta jednej bazy. Odmawia pustych wartości: to one powstają, gdy zmienna nie
        dotrze do kontenera, a klient zbudowany na nich pada dopiero przy pierwszym zapytaniu,
        daleko od przyczyny.

        Example args:
            host="postgres"
            port=5432
            database="helpdesk"
            user="helpdesk"
            password="helpdesk"
            timeout=30.0

        Example result:
            PostgresClient dla postgres:5432/helpdesk, jeszcze bez połączenia

        Raises:
            DbPostgresConfigError: pusty host, baza, użytkownik albo brak hasła
        """
        # --- wartości tekstowe: puste to brak konfiguracji, nie adres ---
        required = (
            ("POSTGRES_HOST", host),
            ("POSTGRES_DB",   database),
            ("POSTGRES_USER", user),
        )

        for name, value in required:
            if not value.strip():
                raise DbPostgresConfigError(f"{name} nie może być puste")

        # --- hasło: w kodzie nie ma wartości domyślnej, podaje je konfiguracja ---
        if password is None or not password.strip():
            raise DbPostgresConfigError("POSTGRES_PASSWORD nie może być puste")

        self._host     = host.strip()
        self._port     = port
        self._database = database.strip()
        self._user     = user.strip()
        self._password = password
        self._timeout  = timeout

        self._pool: asyncpg.Pool | None = None
        # Dwie korutyny pytające naraz po raz pierwszy nie mogą założyć dwóch pul.
        self._pool_lock = asyncio.Lock()

    @property
    def database(self) -> str:
        """
        Description:
        Nazwa bazy, z którą klient się łączy — do komunikatów błędów klas tego pakietu.

        Example args:
            (brak)

        Example result:
            "helpdesk"
        """
        return self._database

    async def fetch_value(
        self,
        sql:   str,     # np. "SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"
        *args: object,  # np. "pl_search"
    ) -> object:
        """
        Description:
        Wykonuje zapytanie i zwraca pierwszą kolumnę pierwszego wiersza (`None`, gdy wierszy nie
        ma).

        Example args:
            sql="SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"
            args=("pl_search",)

        Example result:
            1

        Raises:
            DbPostgresConfigError: jak w `_get_pool()`
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        value = await self._run("fetchval", sql, args)

        return value

    async def fetch_rows(
        self,
        sql:   str,     # np. 'SELECT item_id FROM "docs_text" WHERE body ILIKE $1'
        *args: object,  # np. "%00942%"
    ) -> list[dict[str, object]]:
        """
        Description:
        Wykonuje zapytanie i zwraca wszystkie wiersze jako słowniki kolumna → wartość. Słowniki,
        a nie rekordy sterownika, żeby jego typy nie wychodziły poza ten plik.

        Example args:
            sql='SELECT item_id FROM "docs_text" WHERE body ILIKE $1'
            args=("%00942%",)

        Example result:
            [{"item_id": "usr-komunikat-brak-serwera"}]

        Raises:
            DbPostgresConfigError: jak w `_get_pool()`
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        records = await self._run("fetch", sql, args)
        rows    = [dict(record) for record in records]

        return rows

    async def execute(
        self,
        sql:   str,     # np. 'DROP TABLE IF EXISTS "docs_text"'
        *args: object,  # np. brak
    ) -> None:
        """
        Description:
        Wykonuje polecenie, które nie zwraca wierszy: zakładanie i kasowanie tabel, zapis.

        Example args:
            sql='DROP TABLE IF EXISTS "docs_text"'
            args=()

        Example result:
            None

        Raises:
            DbPostgresConfigError: jak w `_get_pool()`
            DbPostgresError: baza nie odpowiedziała albo odrzuciła polecenie
        """
        await self._run("execute", sql, args)

        return None

    async def aclose(self) -> None:
        """
        Description:
        Zamyka pulę połączeń. Wywołany na kliencie, który nigdy się nie połączył, nic nie robi.

        Example args:
            (brak)

        Example result:
            None
        """
        if self._pool is None:
            return None

        await self._pool.close()
        self._pool = None

        return None

    async def _get_pool(self) -> asyncpg.Pool:
        """
        Description:
        Oddaje pulę połączeń, zakładając ją przy pierwszym wywołaniu. Jedyne miejsce, w którym
        błędy łączenia stają się naszymi: odrzucone hasło i brak bazy to konfiguracja, wszystko
        inne — niedostępna usługa.

        Example args:
            (brak)

        Example result:
            <asyncpg.Pool> z co najmniej jednym otwartym połączeniem

        Raises:
            DbPostgresConfigError: baza odrzuciła hasło albo bazy o tej nazwie nie ma
            DbPostgresError: z bazą nie da się połączyć
        """
        async with self._pool_lock:
            # --- pula już jest ---
            if self._pool is not None:
                return self._pool

            # --- pierwsze użycie: załóż ---
            try:
                self._pool = await asyncpg.create_pool(
                    host            = self._host,
                    port            = self._port,
                    database        = self._database,
                    user            = self._user,
                    password        = self._password,
                    min_size        = POOL_MIN_SIZE,
                    max_size        = POOL_MAX_SIZE,
                    timeout         = self._timeout,  # łączenie
                    command_timeout = self._timeout,  # każde zapytanie
                )
            except asyncpg.InvalidPasswordError as exc:            # hasło odrzucone
                raise DbPostgresConfigError(
                    f"Postgres odrzucił hasło użytkownika '{self._user}' — POSTGRES_PASSWORD "
                    f"działa tylko przy pierwszym starcie na pustym wolumenie"
                ) from exc
            except asyncpg.InvalidCatalogNameError as exc:         # nie ma takiej bazy
                raise DbPostgresConfigError(f"w Postgresie nie ma bazy '{self._database}'") from exc
            except (
                OSError,                 # odmowa połączenia, DNS, zerwany transport
                TimeoutError,            # baza nie odpowiedziała w czasie
                asyncpg.PostgresError,   # serwer odpowiedział błędem
                asyncpg.InterfaceError,  # sterownik nie dogadał się z serwerem
            ) as exc:
                raise DbPostgresError(
                    f"nie da się połączyć z Postgresem {self._host}:{self._port}: {exc}"
                ) from exc

            logger.info(
                "postgres pool host=%s port=%d database=%s", self._host, self._port, self._database
            )

            return self._pool

    async def _run(
        self,
        method: str,                 # "fetchval" | "fetch" | "execute" — metoda puli
        sql:    str,                 # np. "SELECT 1"
        args:   tuple[object, ...],  # np. ()
    ) -> object:
        """
        Description:
        Wykonuje jedno wywołanie na puli. Jedyne miejsce, w którym błędy zapytań stają się
        `DbPostgresError`, więc żaden wołający nie widzi typów sterownika.

        Example args:
            method="fetchval"
            sql="SELECT count(*) FROM pg_ts_config WHERE cfgname = $1"
            args=("pl_search",)

        Example result:
            1

        Raises:
            DbPostgresConfigError: jak w `_get_pool()`
            DbPostgresError: baza nie odpowiedziała albo odrzuciła zapytanie
        """
        pool = await self._get_pool()

        try:
            result = await getattr(pool, method)(sql, *args)
        except (
            OSError,                 # zerwane połączenie
            TimeoutError,            # zapytanie nie zmieściło się w czasie
            asyncpg.PostgresError,   # serwer odrzucił zapytanie
            asyncpg.InterfaceError,  # połączenie zamknięte pod zapytaniem
        ) as exc:
            raise DbPostgresError(f"zapytanie do Postgresa nie powiodło się: {exc}") from exc

        return result
