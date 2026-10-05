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
    """Sprawdza, czy klient z poprawną konfiguracją łączy się z prawdziwą bazą: najprostsze
    zapytanie (`SELECT 1`) dochodzi do serwera i wraca z wynikiem 1.

    Wyłapuje klienta, który nie umie połączyć się z działającą bazą albo nie oddaje jej
    odpowiedzi — wtedy nie działa wyszukiwanie tekstowe ani odczyt wątków zgłoszeń i sekcji
    dokumentacji."""
    client = build_postgres_client()

    try:
        assert await client.fetch_value("SELECT 1") == 1
    finally:
        await client.aclose()


async def test_a_wrong_password_is_a_config_error() -> None:
    """Sprawdza, czy przy złym haśle klient zgłasza błąd konfiguracji (`DbPostgresConfigError`)
    wskazujący zmienną `POSTGRES_PASSWORD`: prawdziwy serwer odrzuca hasło błędem, który klient
    rozpoznaje.

    Wyłapuje serwer, który na złe hasło odpowiada innym błędem, niż klient zakłada: pomyłka
    w konfiguracji wyglądałaby wtedy jak awaria bazy, a komunikat nie mówiłby, co poprawić."""
    client = build_postgres_client(password="na-pewno-nie-to-haslo")

    try:
        with pytest.raises(DbPostgresConfigError, match="POSTGRES_PASSWORD"):
            await client.fetch_value("SELECT 1")
    finally:
        await client.aclose()


async def test_a_missing_database_is_a_config_error() -> None:
    """Sprawdza, czy przy nazwie bazy, której na serwerze nie ma, klient zgłasza błąd konfiguracji
    (`DbPostgresConfigError`) i podaje w nim tę nazwę.

    Wyłapuje serwer, który brak bazy zgłasza innym błędem, niż klient zakłada: literówka w nazwie
    bazy wyglądałaby wtedy jak awaria usługi, bez wskazania, która nazwa jest zła."""
    client = build_postgres_client(database="nie_ma_takiej_bazy")

    try:
        with pytest.raises(DbPostgresConfigError, match="nie_ma_takiej_bazy"):
            await client.fetch_value("SELECT 1")
    finally:
        await client.aclose()
