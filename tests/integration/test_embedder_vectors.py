import math

import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_embedder]

TICKET_TEXT       = "Drukarka nie drukuje po aktualizacji sterownika"
OTHER_TICKET_TEXT = "Terminal płatniczy zgłasza błąd E-104"


def _embed(
    client: httpx2.Client,  # e.g. httpx2.Client(base_url="http://localhost:8001")
    texts:  list[str],      # e.g. ["Drukarka nie drukuje"]
    mode:   str = "passage",
) -> dict:
    """
    Description:
    Calls POST /embed and returns the decoded body, failing the test on any non-200 so the
    assertions below read as statements about vectors, not about HTTP.

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
    """Same text embedded in two separate requests → byte-identical vectors (the stub's point)."""
    first  = _embed(embedder_client, [TICKET_TEXT])
    second = _embed(embedder_client, [TICKET_TEXT])

    assert first["vectors"][0] == second["vectors"][0]


def test_different_texts_yield_different_vectors(embedder_client: httpx2.Client) -> None:
    """Two unrelated texts → different vectors (a constant answer would fake every recall test)."""
    body = _embed(embedder_client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert body["vectors"][0] != body["vectors"][1]


def test_batch_preserves_input_order(embedder_client: httpx2.Client) -> None:
    """Batch of two texts → vectors match the ones returned for each text alone, in order."""
    body = _embed(embedder_client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert body["vectors"][0] == _embed(embedder_client, [TICKET_TEXT])["vectors"][0]
    assert body["vectors"][1] == _embed(embedder_client, [OTHER_TICKET_TEXT])["vectors"][0]


def test_vector_length_matches_reported_dimension(embedder_client: httpx2.Client) -> None:
    """Response → every vector is exactly as long as the dimension the service reports."""
    body = _embed(embedder_client, [TICKET_TEXT, OTHER_TICKET_TEXT])

    assert all(len(vector) == body["dimension"] for vector in body["vectors"])


def test_vectors_are_unit_length(embedder_client: httpx2.Client) -> None:
    """Response → vectors are L2-normalised, so cosine scores land in the production range."""
    body = _embed(embedder_client, [TICKET_TEXT])

    norm = math.sqrt(sum(value * value for value in body["vectors"][0]))

    assert norm == pytest.approx(1.0)


def test_missing_mode_is_rejected(embedder_client: httpx2.Client) -> None:
    """POST /embed without `mode` → 422 (the caller must state the mode, never inherit one)."""
    response = embedder_client.post("/embed", json={"texts": [TICKET_TEXT]})

    assert response.status_code == 422


def test_unknown_mode_is_rejected(embedder_client: httpx2.Client) -> None:
    """POST /embed with a mode outside query/passage/sts → 422 (closed set, not free text)."""
    response = embedder_client.post("/embed", json={"texts": [TICKET_TEXT], "mode": "document"})

    assert response.status_code == 422


def test_empty_batch_is_rejected(embedder_client: httpx2.Client) -> None:
    """POST /embed with an empty text list → 422 (an empty batch is a caller bug, not a no-op)."""
    response = embedder_client.post("/embed", json={"texts": [], "mode": "passage"})

    assert response.status_code == 422
