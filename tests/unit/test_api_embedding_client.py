import httpx
import pytest

from app.embedding import EmbeddingClient, EmbeddingConfigError, EmbeddingError
from tests.helpers_transport import always, capturing, raising, with_transport

BASE_URL = "http://embedder:8000"

# One vector wide enough to be recognisable in assertions, narrow enough to write out.
VECTOR = [0.1, -0.2, 0.3]

# The single answer this client's happy path needs. Passed explicitly rather than defaulted to,
# because the shape is this service's contract, not a shared one.
ONE_VECTOR = {"vectors": [VECTOR]}

# What the embedder answers while a test inspects the REQUEST. This client speaks to one route, so
# the map is a constant instead of a per-test literal (`routed()`'s permissive default would work
# too, but it answers with Qdrant's shape, which would make an assertion here read as an accident).
EMBED_ROUTE = {("POST", "/embed"): httpx.Response(200, json=ONE_VECTOR)}


def _client(handler: httpx.MockTransport) -> EmbeddingClient:
    """
    Description:
    Builds an embedder client answering from a handler instead of a socket. Only the construction
    is local — the rigging itself lives in `with_transport()`, together with the reasoning for
    replacing a private attribute.

    Example args:
        handler=always({"vectors": [[0.1, -0.2, 0.3]]})

    Example result:
        EmbeddingClient answering from the handler
    """
    return with_transport(EmbeddingClient(base_url=BASE_URL), handler)


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
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await getattr(client, method_name)(["Brak tonera"])

    assert seen[0]["body"]["mode"] == expected_mode


async def test_texts_are_sent_as_submitted() -> None:
    """Texts reach the embedder unchanged → prefixing is the model's business, not the client's."""
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await client.embed_passage(["Brak tonera"])

    assert seen[0]["body"]["texts"] == ["Brak tonera"]


async def test_the_batch_goes_to_the_embed_path() -> None:
    """One POST to /embed → the route is part of the contract between two services we ship
    together. Newly assertable: the shared capturing helper records the path, which the old
    body-only double could not."""
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await client.embed_passage(["Brak tonera"])

    assert [(call["method"], call["path"]) for call in seen] == [("POST", "/embed")]


async def test_vectors_are_returned_in_submission_order() -> None:
    """Batch of three → three vectors in the order sent, because retrieval zips them back."""
    client = _client(always({"vectors": [[1.0], [2.0], [3.0]]}))

    vectors = await client.embed_passage(["a", "b", "c"])

    assert vectors == [[1.0], [2.0], [3.0]]


async def test_vector_count_mismatch_is_an_error() -> None:
    """Two texts, one vector back → error, because silently zipping them would misattribute."""
    client = _client(always(ONE_VECTOR))

    with pytest.raises(EmbeddingError, match="1 vector"):
        await client.embed_passage(["a", "b"])


async def test_missing_vectors_field_is_an_error() -> None:
    """200 whose body has no `vectors` → EmbeddingError, not a KeyError from the domain."""
    client = _client(always({"model": "fake"}))

    with pytest.raises(EmbeddingError, match="vectors"):
        await client.embed_passage(["a"])


async def test_server_error_becomes_a_layer_error() -> None:
    """Embedder answers 503 → EmbeddingError; callers never see an httpx type (rule 4)."""
    client = _client(always({"detail": "model down"}, status=503))

    with pytest.raises(EmbeddingError, match="503"):
        await client.embed_passage(["a"])


async def test_connection_failure_becomes_a_layer_error() -> None:
    """Embedder unreachable → EmbeddingError naming the reach failure, not a raw transport error."""
    client = _client(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(EmbeddingError, match="reach"):
        await client.embed_passage(["a"])


async def test_timeout_becomes_a_layer_error() -> None:
    """Embedder exceeds the timeout → EmbeddingError saying so, so indexing can decide to retry."""
    client = _client(raising(httpx.ReadTimeout("too slow")))

    with pytest.raises(EmbeddingError, match="timed out"):
        await client.embed_passage(["a"])


async def test_non_json_body_becomes_a_layer_error() -> None:
    """200 carrying a proxy's HTML error page → EmbeddingError, not a JSON decode error."""
    client = _client(always(text="<html>oops</html>"))

    with pytest.raises(EmbeddingError, match="non-JSON"):
        await client.embed_passage(["a"])
