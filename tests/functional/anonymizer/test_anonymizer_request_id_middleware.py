from fastapi.testclient import TestClient

from anonymizer_app.core_errors.handlers import REQUEST_ID_HEADER
from anonymizer_app.main import create_app


def test_a_request_without_an_id_gets_one() -> None:
    """Sprawdza, czy na żądanie bez nagłówka `X-Request-ID` usługa `anonymizer` odpowiada
    z własnym, niepustym identyfikatorem, innym przy każdym kolejnym żądaniu.

    Wyłapuje usługę bez warstwy nadającej identyfikator albo z identyfikatorem stałym: wpisów
    logu jednego żądania nie dałoby się powiązać, a różnych — rozróżnić."""
    client = TestClient(create_app())

    first  = client.get("/health").headers.get(REQUEST_ID_HEADER)
    second = client.get("/health").headers.get(REQUEST_ID_HEADER)

    assert first
    assert first != second


def test_the_id_from_the_api_is_kept() -> None:
    """Sprawdza, czy usługa odsyła bez zmian identyfikator, który `api` podało w nagłówku
    `X-Request-ID`, także w treści błędu.

    Wyłapuje nadpisanie przysłanego identyfikatora własnym: jeden identyfikator ma spinać logi
    obu usług, a po podmianie wpisów anonimizatora nie dałoby się powiązać z żądaniem w `api`."""
    client = TestClient(create_app())

    response = client.post("/anonymize", json={}, headers={REQUEST_ID_HEADER: "id-from-api"})

    assert response.headers[REQUEST_ID_HEADER] == "id-from-api"
    assert response.json()["request_id"]       == "id-from-api"
