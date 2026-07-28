import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_embedder]


def test_health_returns_ok(embedder_client: httpx2.Client) -> None:
    """GET /health on the running embedder → 200 with status "ok"."""
    response = embedder_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_body_exposes_no_configuration(embedder_client: httpx2.Client) -> None:
    """Health payload → only the status key (a public probe must not leak model or dimension)."""
    response = embedder_client.get("/health")

    assert set(response.json()) == {"status"}
