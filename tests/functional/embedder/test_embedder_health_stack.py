import httpx2
import pytest

pytestmark = [pytest.mark.stack, pytest.mark.stack_embedder]

# Deployment smoke only: the payload shape is proven in-process by
# tests/functional/embedder/test_embedder_health_endpoint.py. What a container adds is the proof
# that the image built, the CMD points at the right module and the published port reaches the app.


def test_health_answers_over_the_published_port(embedder_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener embeddera odpowiada na `GET /health` przez port
    wystawiony na hosta: status 200 i treść `{"status": "ok"}`.

    Wyłapuje usterkę wdrożenia, której testy w procesie nie widzą: obraz się nie zbudował,
    kontener uruchamia nie ten moduł albo port nie jest wystawiony."""
    response = embedder_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
