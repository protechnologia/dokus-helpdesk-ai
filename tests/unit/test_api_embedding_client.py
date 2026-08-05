import json

import httpx
import pytest

from app.embedding import EmbeddingClient, EmbeddingConfigError, EmbeddingError

# One vector wide enough to be recognisable in assertions, narrow enough to write out.
VECTOR = [0.1, -0.2, 0.3]


def _client(handler: httpx.MockTransport) -> EmbeddingClient:
    """
    Description:
    Builds a client whose transport is a handler instead of a socket, so the contract is tested
    without a running embedder. The private attribute is replaced deliberately: `httpx` offers no
    public seam for this, and inventing a constructor argument only tests would use would put
    test scaffolding into production code.

    Example args:
        handler=httpx.MockTransport(lambda request: httpx.Response(200, json={...}))

    Example result:
        EmbeddingClient answering from the handler
    """
    client         = EmbeddingClient(base_url="http://embedder:8000")
    client._client = httpx.AsyncClient(transport=handler, base_url="http://embedder:8000")

    return client


def _responding(payload: dict | None = None, status: int = 200) -> httpx.MockTransport:
    """
    Description:
    Builds a transport answering every request with one canned response. For tests where the
    ANSWER is the subject — counts, shapes, statuses.

    Example args:
        payload={"vectors": [[0.1, -0.2, 0.3]]}
        status=200

    Example result:
        httpx.MockTransport returning 200 with that body
    """
    body = payload if payload is not None else {"vectors": [VECTOR]}

    return httpx.MockTransport(lambda request: httpx.Response(status, json=body))


def _capturing(seen: dict) -> httpx.MockTransport:
    """
    Description:
    Builds a transport that records the request body into `seen` and answers with one vector. The
    counterpart of `_responding()`: for tests where the REQUEST is the subject — which mode was
    actually put on the wire.

    Example args:
        seen={}

    Example result:
        httpx.MockTransport filling `seen` with {"texts": [...], "mode": "passage"}
    """

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))

        return httpx.Response(200, json={"vectors": [VECTOR]})

    return httpx.MockTransport(handler)


def _raising(error: Exception) -> httpx.MockTransport:
    """
    Description:
    Builds a transport that fails the way a broken connection does, rather than answering.

    Example args:
        error=httpx.ConnectError("connection refused")

    Example result:
        httpx.MockTransport raising that error on every request
    """

    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    return httpx.MockTransport(handler)


def test_empty_base_url_is_refused_at_build_time() -> None:
    """EMBEDDING_BASE_URL="" (what compose substitutes for an unset var) → error at construction."""
    with pytest.raises(EmbeddingConfigError, match="EMBEDDING_BASE_URL"):
        EmbeddingClient(base_url="")


def test_whitespace_base_url_is_refused_at_build_time() -> None:
    """Base URL of blanks → treated as missing, not as a URL made of spaces."""
    with pytest.raises(EmbeddingConfigError):
        EmbeddingClient(base_url="   ")


# One test per mode rather than a loop: the point is that each named method is wired to its own
# vector space, and a parametrised failure has to say WHICH method broke without decoding an id.
@pytest.mark.parametrize(
    ("method_name", "expected_mode"),
    [
        ("embed_query",   "query"),    # new tickets asked against the index
        ("embed_passage", "passage"),  # historical tickets being indexed
        ("embed_sts",     "sts"),      # symmetric ticket-to-ticket comparison
    ],
)
async def test_each_method_sends_its_own_mode(method_name: str, expected_mode: str) -> None:
    """embed_<mode>() → that mode on the wire; a method wired to the wrong space is undetectable
    later, because the vectors still look valid."""
    seen: dict = {}
    client     = _client(_capturing(seen))

    await getattr(client, method_name)(["Brak tonera"])

    assert seen["mode"] == expected_mode


async def test_texts_are_sent_as_submitted() -> None:
    """Texts reach the embedder unchanged → prefixing is the model's business, not the client's."""
    seen: dict = {}
    client     = _client(_capturing(seen))

    await client.embed_passage(["Brak tonera"])

    assert seen["texts"] == ["Brak tonera"]


async def test_vectors_are_returned_in_submission_order() -> None:
    """Batch of three → three vectors in the order sent, because retrieval zips them back."""
    client = _client(_responding({"vectors": [[1.0], [2.0], [3.0]]}))

    vectors = await client.embed_passage(["a", "b", "c"])

    assert vectors == [[1.0], [2.0], [3.0]]


async def test_vector_count_mismatch_is_an_error() -> None:
    """Two texts, one vector back → error, because silently zipping them would misattribute."""
    client = _client(_responding())

    with pytest.raises(EmbeddingError, match="1 vector"):
        await client.embed_passage(["a", "b"])


async def test_missing_vectors_field_is_an_error() -> None:
    """200 whose body has no `vectors` → EmbeddingError, not a KeyError from the domain."""
    client = _client(_responding({"model": "fake"}))

    with pytest.raises(EmbeddingError, match="vectors"):
        await client.embed_passage(["a"])


async def test_server_error_becomes_a_layer_error() -> None:
    """Embedder answers 503 → EmbeddingError; callers never see an httpx type (rule 4)."""
    client = _client(_responding({"detail": "model down"}, status=503))

    with pytest.raises(EmbeddingError, match="503"):
        await client.embed_passage(["a"])


async def test_connection_failure_becomes_a_layer_error() -> None:
    """Embedder unreachable → EmbeddingError naming the reach failure, not a raw transport error."""
    client = _client(_raising(httpx.ConnectError("connection refused")))

    with pytest.raises(EmbeddingError, match="reach"):
        await client.embed_passage(["a"])


async def test_timeout_becomes_a_layer_error() -> None:
    """Embedder exceeds the timeout → EmbeddingError saying so, so indexing can decide to retry."""
    client = _client(_raising(httpx.ReadTimeout("too slow")))

    with pytest.raises(EmbeddingError, match="timed out"):
        await client.embed_passage(["a"])


async def test_non_json_body_becomes_a_layer_error() -> None:
    """200 carrying a proxy's HTML error page → EmbeddingError, not a JSON decode error."""
    client = _client(httpx.MockTransport(lambda r: httpx.Response(200, text="<html>oops</html>")))

    with pytest.raises(EmbeddingError, match="non-JSON"):
        await client.embed_passage(["a"])
