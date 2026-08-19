import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_api]

# The DEPLOYMENT half for POST /search: that the router is mounted in the built image and reachable
# over the published port. Nothing here re-checks the response shape — unit tests on TestClient
# prove that in-process (CLAUDE.md -> "Testy": contract in-process, deployment over HTTP).
#
# Deliberately asserts on a request that needs NO dependency: an empty body is refused by our own
# model before the LLM, the embedder or Qdrant are touched. Whether a real search returns sensible
# hits is the `functional` axis (stage 5.6), which needs a model and a populated collection.


def test_search_validates_the_request_in_the_container(api_client: httpx2.Client) -> None:
    """POST /search without a body on the running api → 422, not 404: the route is mounted and
    wired to our request model, proven without any dependency being reachable."""
    response = api_client.post("/search", json={"ticket_id": "integration-smoke"})

    assert response.status_code == 422
