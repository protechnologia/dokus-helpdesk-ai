import httpx2
import pytest

from app.errors import REQUEST_ID_HEADER

pytestmark = [pytest.mark.integration, pytest.mark.integration_api]

# This is the DEPLOYMENT half of the split from CLAUDE.md -> "Testy". Nothing here re-checks the
# response shape — unit tests on TestClient already prove that, and repeating it would only make
# the marked run longer. What only a container can prove is that the image built, the CMD points
# at the right module, the published port reaches it and the environment arrived.


def test_health_answers_over_the_published_port(api_client: httpx2.Client) -> None:
    """GET /health on the running api → 200 with status "ok" (image, CMD and port all wired)."""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_response_carries_a_request_id(api_client: httpx2.Client) -> None:
    """Any response from the running api → X-Request-ID header (middleware is actually mounted)."""
    response = api_client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_request_id_from_the_caller_is_echoed_back(api_client: httpx2.Client) -> None:
    """Caller-supplied X-Request-ID → echoed unchanged, so one id spans api and embedder."""
    correlation_id = "integration-smoke-0e2"

    response = api_client.get("/health", headers={REQUEST_ID_HEADER: correlation_id})

    assert response.headers.get(REQUEST_ID_HEADER) == correlation_id
