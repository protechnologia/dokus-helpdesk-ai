import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_embedder]

# Deployment smoke only: the payload shape is proven in-process by
# tests/unit/test_embedder_health_endpoint.py. What a container adds is the proof that the image
# built, the CMD points at the right module and the published port reaches the app.


def test_health_answers_over_the_published_port(embedder_client: httpx2.Client) -> None:
    """GET /health on the running embedder → 200 with status "ok" (image, CMD and port wired)."""
    response = embedder_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
