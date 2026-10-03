from fastapi.testclient import TestClient

from app.errors import REQUEST_ID_HEADER
from app.main import create_app


def test_response_carries_generated_request_id() -> None:
    """Request without the header → response carries a generated, non-empty id."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_upstream_request_id_is_propagated() -> None:
    """Caller supplies an id → the same id comes back (one id spans several services)."""
    client = TestClient(create_app())

    response = client.get("/health", headers={REQUEST_ID_HEADER: "id-from-caller"})

    assert response.headers[REQUEST_ID_HEADER] == "id-from-caller"


def test_generated_ids_differ_between_requests() -> None:
    """Two requests without the header → two different ids (correlation would be useless)."""
    client = TestClient(create_app())

    first  = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second
