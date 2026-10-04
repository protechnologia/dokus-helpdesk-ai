"""
Description:
Test integracyjny klienta Postgresa z prawdziwą bazą: czy to, co klient zakłada o serwerze, jest
prawdą. Wymaga działającego stacku.

| scenariusz            | oczekiwanie                                                 |
|-----------------------|-------------------------------------------------------------|
| poprawna konfiguracja | zapytanie dochodzi do bazy i wraca z odpowiedzią            |
| złe hasło             | `DbPostgresConfigError` — serwer naprawdę odrzuca hasło     |
| nieistniejąca baza    | `DbPostgresConfigError` — serwer naprawdę zgłasza brak bazy |

O czym pamiętać przy zmianach:

- Tłumaczenie błędów sterownika i kształt zapytań sprawdzają testy jednostkowe na podmienionej
  puli. Tu zostaje tylko to, czego bez serwera nie da się dowieść: jakim błędem odpowiada.
- To test samego klienta, więc woła go wprost; reszta aplikacji używa klas tabel.
- Zachowanie słownika (odmiana, zaprzeczenia, kody) ma własny plik:
  `tests/integration/postgres/test_postgres_text_search_stack.py`.
"""

import pytest

from app.db_postgres import DbPostgresConfigError
from tests.conftest import build_postgres_client

pytestmark = [pytest.mark.stack, pytest.mark.stack_postgres]


async def test_a_query_reaches_the_database() -> None:
    """Poprawna konfiguracja → zapytanie dochodzi do bazy i wraca z odpowiedzią."""
    client = build_postgres_client()

    try:
        assert await client.fetch_value("SELECT 1") == 1
    finally:
        await client.aclose()


async def test_a_wrong_password_is_a_config_error() -> None:
    """Złe hasło → DbPostgresConfigError: serwer odrzuca je błędem, który klient rozpoznaje jako
    konfigurację, a nie awarię."""
    client = build_postgres_client(password="na-pewno-nie-to-haslo")

    try:
        with pytest.raises(DbPostgresConfigError, match="POSTGRES_PASSWORD"):
            await client.fetch_value("SELECT 1")
    finally:
        await client.aclose()


async def test_a_missing_database_is_a_config_error() -> None:
    """Baza o nieistniejącej nazwie → DbPostgresConfigError z tą nazwą."""
    client = build_postgres_client(database="nie_ma_takiej_bazy")

    try:
        with pytest.raises(DbPostgresConfigError, match="nie_ma_takiej_bazy"):
            await client.fetch_value("SELECT 1")
    finally:
        await client.aclose()
