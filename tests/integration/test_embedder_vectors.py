import httpx2
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.integration_embedder]

# The one truth in this project that lives OUTSIDE our code: that the model actually distinguishes
# the three prefix modes. Everything we can prove ourselves — that the right prefix is prepended,
# that a mode reaches the service, that vectors come back in order — is covered in-process by
# tests/unit, and repeating it here would only lengthen a run that needs the stack.
#
# Why this one is worth the stack: the architecture rests on it. Two named vectors per record, the
# "never mix modes in one vector space" rule and the whole stage-3 measurement assume a prefix
# changes the answer. If it did not, `[sts]: ` would be decoration and half the index would be
# waste — and nothing else in the suite would notice.
#
# This file replaced the fake's determinism tests (same text -> same vector, across HTTP). They
# duplicated tests/unit/test_embedder_vectors.py while proving less: the regression they claimed to
# guard against — a mapping deterministic within a process but not across processes — needs a
# RESTART to surface, and calling the same uvicorn twice cannot show it. The golden-value test in
# tests/unit catches that mutation instantly and without a stack.

TICKET_TEXT = "Nie udało się skomunikować z serwerem podczas podpisywania dokumentu"

# Measured against PolDense-150M on 2026-08-05: query↔passage 0.544, passage↔sts 0.814. The
# ceiling sits far above both, so ordinary variation between model families cannot trip it — only
# a model that ignores the prefix outright, which is exactly the failure worth catching. Rival
# models in stage 3 will land elsewhere on this scale and must still pass.
MAX_COSINE_BETWEEN_MODES = 0.98


def _embed(
    client: httpx2.Client,  # e.g. httpx2.Client(base_url="http://localhost:8001")
    text:   str,            # e.g. "Nie udało się skomunikować z serwerem"
    mode:   str,            # e.g. "query"
) -> dict:
    """
    Description:
    Embeds one text in one mode and returns the decoded body, failing the test on any non-200 so
    the assertions below read as statements about vectors, not about HTTP.

    Example args:
        client=httpx2.Client(base_url="http://localhost:8001")
        text="Nie udało się skomunikować z serwerem"
        mode="query"

    Example result:
        {"vectors": [[0.01, -0.04]], "model": "OPI-PIB/PolDense-150M", "dimension": 768}
    """
    response = client.post("/embed", json={"texts": [text], "mode": mode})

    assert response.status_code == 200, response.text

    return response.json()


def _cosine(
    first:  list[float],  # e.g. [0.1, -0.2, 0.3]
    second: list[float],  # e.g. [0.4, 0.5, -0.6]
) -> float:
    """
    Description:
    Cosine similarity of two vectors, computed as a plain dot product. Valid only because the
    encoder normalises its output to unit length — which `test_vectors_are_unit_length` asserts,
    so this shortcut cannot quietly become wrong.

    Example args:
        first=[1.0, 0.0]
        second=[0.0, 1.0]

    Example result:
        0.0
    """
    return sum(a * b for a, b in zip(first, second, strict=True))


@pytest.fixture
def passage_body(embedder_client: httpx2.Client) -> dict:
    """
    Description:
    Embeds the sample text as a passage and refuses to continue if the service is running the
    fake backend, which ignores modes by construction. A hard failure rather than a skip: these
    tests sit behind a marker, so asking for them means the stack is meant to run a real model
    (CLAUDE.md -> "Testy"). A skip would be the worst outcome — the suite would look green while
    the single fact it exists to verify went unchecked.

    Example args:
        embedder_client=httpx2.Client(base_url="http://localhost:8001")

    Example result:
        {"vectors": [[0.01, -0.04]], "model": "OPI-PIB/PolDense-150M", "dimension": 768}
    """
    body = _embed(embedder_client, TICKET_TEXT, "passage")

    assert body["model"] != "fake", (
        "prefix modes cannot be verified against the fake backend, which ignores them; "
        "the composition defaults to a real model — check EMBEDDING_BACKEND"
    )

    return body


def test_vectors_are_unit_length(passage_body: dict) -> None:
    """Real model → unit-length vectors, so RAG_SCORE_MIN means the same as it does on the fake."""
    vector = passage_body["vectors"][0]

    assert _cosine(vector, vector) == pytest.approx(1.0, abs=1e-4)


def test_reported_dimension_matches_the_vectors(passage_body: dict) -> None:
    """Reported `dimension` equals the actual width → the Qdrant collection can trust the header."""
    assert len(passage_body["vectors"][0]) == passage_body["dimension"]


@pytest.mark.parametrize(
    "mode",
    [
        "query",  # asymmetric retrieval: a question asked against indexed documents
        "sts",    # symmetric comparison: dedup and "similar cases"
    ],
)
def test_mode_changes_the_vector(
    embedder_client: httpx2.Client,
    passage_body:    dict,
    mode:            str,
) -> None:
    """Same text under another mode → a different vector, because the model was TRAINED on the
    prefix; equality here would mean the second named vector is storage spent on nothing."""
    other = _embed(embedder_client, TICKET_TEXT, mode)["vectors"][0]

    assert _cosine(other, passage_body["vectors"][0]) < MAX_COSINE_BETWEEN_MODES
