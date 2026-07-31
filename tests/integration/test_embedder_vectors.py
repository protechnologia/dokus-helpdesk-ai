import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_embedder]

# Deliberately thin. Request validation, batch ordering, vector width and L2 normalisation are
# facts about our own code, proven in-process by tests/unit/test_embedder_embed_endpoint.py —
# repeating them here would only lengthen a run that needs the stack (CLAUDE.md -> "Testy").
#
# What survives is what a TestClient cannot show: that the mapping text -> vector holds ACROSS A
# PROCESS BOUNDARY. A stub that quietly became per-process (a random seed, a warm cache) would keep
# every unit test green while indexed vectors stopped matching freshly computed ones.

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


def _embed(
    client: httpx2.Client,  # e.g. httpx2.Client(base_url="http://localhost:8001")
    texts:  list[str],      # e.g. ["Drukarka nie drukuje"]
    mode:   str = "passage",
) -> dict:
    """
    Description:
    Calls POST /embed on the running service and returns the decoded body, failing the test on any
    non-200 so the assertions below read as statements about vectors, not about HTTP.

    Example args:
        client=httpx2.Client(base_url="http://localhost:8001")
        texts=["Drukarka nie drukuje"]
        mode="passage"

    Example result:
        {"vectors": [[0.01, -0.04]], "model": "stub-deterministic", "dimension": 768}
    """
    response = client.post("/embed", json={"texts": texts, "mode": mode})

    assert response.status_code == 200, response.text

    return response.json()


def test_same_text_yields_identical_vector(embedder_client: httpx2.Client) -> None:
    """Same text in two HTTP requests → identical vectors (determinism survives the wire)."""
    first  = _embed(embedder_client, [TICKET_TEXT])
    second = _embed(embedder_client, [TICKET_TEXT])

    assert first["vectors"][0] == second["vectors"][0]


def test_different_texts_yield_different_vectors(embedder_client: httpx2.Client) -> None:
    """Two unrelated texts → different vectors (a constant answer would fake every recall test)."""
    body = _embed(embedder_client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert body["vectors"][0] != body["vectors"][1]
