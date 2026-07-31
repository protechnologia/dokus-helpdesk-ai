from fastapi.testclient import TestClient

from embedder_app.main import create_app


def test_health_returns_ok() -> None:
    """GET /health on a freshly assembled app → 200 with status "ok"."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_body_exposes_no_configuration() -> None:
    """Health payload → only the status key (a public probe must not leak model or dimension)."""
    client = TestClient(create_app())

    response = client.get("/health")

    # This service knows the model name and the vector width, so the temptation to expose them on
    # a public liveness probe is real — and the probe is reachable by anyone who reaches the port.
    assert set(response.json()) == {"status"}
