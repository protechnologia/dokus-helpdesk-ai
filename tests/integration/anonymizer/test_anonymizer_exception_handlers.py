import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from anonymizer_app.engine import EngineConfigError, EngineError
from anonymizer_app.errors import register_exception_handlers
from tests._helpers.anonymization import RAW_TEXT, SENSITIVE


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Naga aplikacja z samymi handlerami usługi `anonymizer` i trasami, które prowokują błąd.
    Prawdziwa usługa uzależniłaby te asercje od tego, jakie trasy akurat istnieją. Błąd silnika
    cytuje zgłoszenie, tak jak potrafi to zrobić biblioteka prawdziwego silnika.

    Example args:
        (brak)

    Example result:
        TestClient nad aplikacją z /boom, /engine-down i /engine-misconfigured
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/engine-down")
    async def engine_down() -> None:
        raise EngineError(f"model NER padł na tekście: {RAW_TEXT}")

    @app.get("/engine-misconfigured")
    async def engine_misconfigured() -> None:
        raise EngineConfigError("nieznany ANONYMIZATION_ENGINE='ner'")

    # raise_server_exceptions=False: odpowiadają handlery, zamiast wyjątku wpadającego do testu.
    return TestClient(app, raise_server_exceptions=False)


def test_an_http_exception_keeps_its_status_and_the_common_shape(client: TestClient) -> None:
    """Sprawdza, czy błąd zgłoszony przez trasę (`HTTPException` ze statusem 404) wraca z tym
    samym statusem, opisem w polu `detail` i polem `request_id`.

    Wyłapuje obsługę błędów, która zmienia status albo kształt: `api` czyta jeden kształt błędu
    ze wszystkich usług."""
    response = client.get("/boom")

    assert response.status_code     == 404
    assert response.json()["detail"] == "Not Found"
    assert "request_id" in response.json()


def test_an_engine_failure_is_503_without_its_message(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Sprawdza, czy awaria silnika wraca jako 503 z ogólnym opisem „Anonymization failed", a ani
    odpowiedź, ani log usługi (na żadnym poziomie) nie zawierają komunikatu wyjątku, który tu
    cytuje zgłoszenie z danymi osobowymi.

    Wyłapuje surowe 500 zamiast „spróbuj później" oraz przeciek zgłoszenia przez komunikat
    biblioteki — do odpowiedzi, którą loguje `api`, albo do logu tej usługi."""
    with caplog.at_level(logging.DEBUG):
        response = client.get("/engine-down")

    assert response.status_code     == 503
    assert response.json()["detail"] == "Anonymization failed"
    assert not [fragment for fragment in SENSITIVE if fragment in response.text]
    assert not [fragment for fragment in SENSITIVE if fragment in caplog.text]


def test_a_config_error_is_not_dressed_up_as_a_transient_failure(client: TestClient) -> None:
    """Sprawdza, czy błąd konfiguracji silnika kończy żądanie statusem 500, a nie 503, choć
    w kodzie jest odmianą awarii silnika, która daje 503.

    Wyłapuje złą konfigurację przebraną za chwilową awarię: 503 znaczy „spróbuj za chwilę",
    a przy błędnej konfiguracji czekanie nic nie da."""
    response = client.get("/engine-misconfigured")

    assert response.status_code == 500
