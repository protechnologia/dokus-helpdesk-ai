import httpx2
import pytest

pytestmark = [pytest.mark.stack, pytest.mark.stack_api]

# The DEPLOYMENT half for POST /search: that the router is mounted in the built image and reachable
# over the published port. Nothing here re-checks the response shape — unit tests on TestClient
# prove that in-process (CLAUDE.md -> "Testy": contract in-process, deployment over HTTP).
#
# Deliberately asserts on a request that needs NO dependency: an empty body is refused by our own
# model before the LLM, the embedder or Qdrant are touched. Whether a real search returns sensible
# hits is the `functional` axis (stage 5.6), which needs a model and a populated collection.


def test_search_validates_the_request_in_the_container(api_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener `api` odrzuca `POST /search` bez opisu zgłoszenia
    statusem 422, a nie 404. Takie żądanie odpada już na sprawdzeniu pól, więc test nie
    potrzebuje modelu, embeddera ani Qdranta.

    Wyłapuje wdrożenie, w którym trasy `/search` nie ma w zbudowanym obrazie albo nie jest
    podpięta do naszego modelu żądania: status 404 znaczyłby, że kontener tej trasy nie zna."""
    response = api_client.post("/search", json={"ticket_id": "integration-smoke"})

    assert response.status_code == 422
