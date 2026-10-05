from fastapi.testclient import TestClient

from embedder_app.errors import REQUEST_ID_HEADER
from embedder_app.main import create_app


def test_response_carries_generated_request_id() -> None:
    """Sprawdza, czy na żądanie bez nagłówka `X-Request-ID` embedder odpowiada z własnym,
    niepustym identyfikatorem żądania w tym nagłówku.

    Wyłapuje aplikację bez warstwy nadającej identyfikator żądania: wpisów logu jednego żądania
    nie dałoby się wtedy ze sobą powiązać."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_upstream_request_id_is_propagated() -> None:
    """Sprawdza, czy embedder odsyła bez zmian identyfikator żądania, który wołający (usługa `api`)
    podał w nagłówku `X-Request-ID`.

    Wyłapuje nadpisanie przysłanego identyfikatora własnym: jeden identyfikator ma spinać logi
    obu usług, a po podmianie wpisów embeddera nie dałoby się powiązać z żądaniem w `api`."""
    client = TestClient(create_app())

    response = client.get("/health", headers={REQUEST_ID_HEADER: "id-from-api"})

    assert response.headers[REQUEST_ID_HEADER] == "id-from-api"


def test_generated_ids_differ_between_requests() -> None:
    """Sprawdza, czy dwa kolejne żądania bez nagłówka `X-Request-ID` dostają dwa różne
    identyfikatory.

    Wyłapuje identyfikator stały albo powtarzający się: wpisy różnych żądań zlałyby się wtedy
    w logach w jedno i identyfikator do niczego by nie służył."""
    client = TestClient(create_app())

    first  = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second


def test_error_response_carries_the_request_id() -> None:
    """Sprawdza, czy odpowiedź na błędne żądanie w pełnej aplikacji embeddera (tu `/embed` bez
    trybu, status 422) niesie ten sam identyfikator żądania w treści błędu i w nagłówku.

    Wyłapuje obsługę błędów, która nie widzi identyfikatora nadanego żądaniu: w treści błędu
    byłby wtedy pusty albo inny niż w nagłówku i w logach."""
    client = TestClient(create_app())

    response = client.post("/embed", json={"texts": ["Brak tonera"]})   # no `mode` → 422

    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]
