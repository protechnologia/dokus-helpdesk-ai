from fastapi.testclient import TestClient

from embedder_app.errors import REQUEST_ID_HEADER
from embedder_app.main import create_app


def test_response_carries_generated_request_id() -> None:
    """Request without the header → response carries a generated, non-empty id."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_upstream_request_id_is_propagated() -> None:
    """`api` supplies an id → the same id comes back (one id spans both services)."""
    client = TestClient(create_app())

    response = client.get("/health", headers={REQUEST_ID_HEADER: "id-from-api"})

    assert response.headers[REQUEST_ID_HEADER] == "id-from-api"


def test_generated_ids_differ_between_requests() -> None:
    """Two requests without the header → two different ids (correlation would be useless)."""
    client = TestClient(create_app())

    first  = client.get("/health").headers[REQUEST_ID_HEADER]
    second = client.get("/health").headers[REQUEST_ID_HEADER]

    assert first != second


def test_error_response_carries_the_request_id() -> None:
    """Failing request in the real app → same id in the body and in the response header."""
    client = TestClient(create_app())

    response = client.post("/embed", json={"texts": ["Brak tonera"]})   # no `mode` → 422

    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]
