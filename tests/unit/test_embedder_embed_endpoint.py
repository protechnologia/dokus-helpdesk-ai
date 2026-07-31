import math

import pytest
from fastapi.testclient import TestClient

from embedder_app.main import create_app

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Builds the real embedder application in-process. This is the CONTRACT half of the split from
    CLAUDE.md -> "Testy": status codes, request validation and payload shape are facts about our
    own code, so they are proven here rather than against a running container.

    Example args:
        (injected by pytest)

    Example result:
        TestClient over the app serving GET /health and POST /embed
    """
    return TestClient(create_app())


def _embed(
    client: TestClient,     # e.g. TestClient(create_app())
    texts:  list[str],      # e.g. ["Drukarka nie drukuje"]
    mode:   str = "passage",
) -> dict:
    """
    Description:
    Posts a batch to /embed and returns the decoded body, failing on any non-200 so the
    assertions below read as statements about vectors rather than about HTTP.

    Example args:
        client=TestClient(create_app())
        texts=["Drukarka nie drukuje"]
        mode="passage"

    Example result:
        {"vectors": [[0.01, -0.04]], "model": "stub-deterministic", "dimension": 768}
    """
    response = client.post("/embed", json={"texts": texts, "mode": mode})

    assert response.status_code == 200, response.text

    return response.json()


def test_missing_mode_is_rejected(client: TestClient) -> None:
    """POST /embed without `mode` → 422 (the caller must state the mode, never inherit one)."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT]})

    assert response.status_code == 422


def test_unknown_mode_is_rejected(client: TestClient) -> None:
    """POST /embed with a mode outside query/passage/sts → 422 (closed set, not free text)."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT], "mode": "document"})

    assert response.status_code == 422


def test_empty_batch_is_rejected(client: TestClient) -> None:
    """POST /embed with an empty text list → 422 (an empty batch is a caller bug, not a no-op)."""
    response = client.post("/embed", json={"texts": [], "mode": "passage"})

    assert response.status_code == 422


def test_missing_texts_is_rejected(client: TestClient) -> None:
    """POST /embed without the `texts` key → 422 (a missing batch is not an empty batch)."""
    response = client.post("/embed", json={"mode": "passage"})

    assert response.status_code == 422


@pytest.mark.parametrize("mode", ["query", "passage", "sts"])
def test_every_declared_mode_is_accepted(client: TestClient, mode: str) -> None:
    """Each of the three declared modes → 200 (the closed set must not reject its own members)."""
    response = client.post("/embed", json={"texts": [TICKET_TEXT], "mode": mode})

    assert response.status_code == 200


def test_batch_preserves_input_order(client: TestClient) -> None:
    """Batch of two texts → vectors match the ones returned for each text alone, in order."""
    body = _embed(client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert body["vectors"][0] == _embed(client, [TICKET_TEXT])["vectors"][0]
    assert body["vectors"][1] == _embed(client, [OTHER_TICKET_TEXT])["vectors"][0]


def test_vector_length_matches_reported_dimension(client: TestClient) -> None:
    """Response → every vector is exactly as long as the dimension the service reports."""
    body = _embed(client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert all(len(vector) == body["dimension"] for vector in body["vectors"])


def test_vectors_are_unit_length(client: TestClient) -> None:
    """Response → vectors are L2-normalised, so cosine scores land in the production range."""
    body = _embed(client, [TICKET_TEXT])

    norm = math.sqrt(sum(value * value for value in body["vectors"][0]))

    assert norm == pytest.approx(1.0)


def test_response_names_the_model_that_produced_the_vectors(client: TestClient) -> None:
    """Response → carries a non-empty model name (a collection is bound to it, not just to size)."""
    body = _embed(client, [TICKET_TEXT])

    assert body["model"]
