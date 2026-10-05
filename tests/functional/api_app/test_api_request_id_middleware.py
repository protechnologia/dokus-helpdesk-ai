from fastapi.testclient import TestClient

from app.errors import REQUEST_ID_HEADER
from app.main import create_app


def test_response_carries_generated_request_id() -> None:
    """Sprawdza, czy odpowiedź na żądanie bez nagłówka `X-Request-ID` niesie ten nagłówek
    z niepustym identyfikatorem nadanym przez aplikację.

    Wyłapuje aplikację, która nie nadaje żądaniu identyfikatora: wołający nie miałby wtedy czego
    podać, żeby odszukać w logach wpisy swojego żądania."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_upstream_request_id_is_propagated() -> None:
    """Sprawdza, czy identyfikator podany przez wołającego w nagłówku `X-Request-ID` wraca
    w odpowiedzi bez zmian.

    Wyłapuje aplikację, która zastępuje cudzy identyfikator własnym: jeden identyfikator nie
    spinałby wtedy logów kilku usług obsługujących to samo żądanie."""
    client = TestClient(create_app())

    response = client.get("/health", headers={REQUEST_ID_HEADER: "id-from-caller"})

    assert response.headers[REQUEST_ID_HEADER] == "id-from-caller"


def test_generated_ids_differ_between_requests() -> None:
    """Sprawdza, czy dwa kolejne żądania bez nagłówka `X-Request-ID` dostają dwa różne
    identyfikatory.

    Wyłapuje identyfikator stały albo powtarzany: wpisy logu różnych żądań miałyby wtedy ten sam
    identyfikator i nie dałoby się ich rozdzielić."""
    client = TestClient(create_app())

    first  = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second
