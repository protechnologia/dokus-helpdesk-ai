import httpx
import pytest

from app.retrieval import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    QdrantClient,
    RetrievalConfigError,
    RetrievalError,
    TicketPoint,
)
from tests.helpers_transport import capturing, raising, routed, with_transport

BASE_URL   = "http://qdrant:6333"
COLLECTION = "tickets"
SIZE       = 768

# The two paths every test routes on, spelled once: they appear in most `routed()` maps, and
# rebuilding them inline made the keys longer than the line limit.
PATH_COLLECTION = f"/collections/{COLLECTION}"
PATH_POINTS     = f"{PATH_COLLECTION}/points"

# One point, built by hand rather than through ParsedTicket: this file tests the CLIENT, and going
# through the domain model would make a schema change fail here for a reason that has nothing to
# do with transport.
POINT = TicketPoint(
    point_id       = "df3b51f3-9eac-56f3-9f28-6253f23dd731",
    vector_problem = [0.1, -0.2],
    vector_sts     = [0.3, -0.4],
    payload        = {"ticket_id": "33644"},
)


def _client(handler: httpx.MockTransport) -> QdrantClient:
    """
    Description:
    Builds a Qdrant client answering from a handler instead of a socket. Only the construction is
    local — the rigging itself lives in `with_transport()`, together with the reasoning for
    replacing a private attribute.

    Example args:
        handler=routed({("GET", "/collections/tickets"): httpx.Response(404)})

    Example result:
        QdrantClient answering from the handler
    """
    return with_transport(QdrantClient(base_url=BASE_URL, collection=COLLECTION), handler)


def _collection_of(size: int, names: tuple[str, ...]) -> httpx.Response:
    """
    Description:
    Builds the description Qdrant returns for an existing collection, with the given named vectors
    at the given size. Lets the schema-check tests state their case in one line.

    Example args:
        size=768
        names=("problem", "sts")

    Example result:
        httpx.Response(200, json={"result": {"config": {"params": {"vectors": {…}}}}})
    """
    vectors = {name: {"size": size, "distance": "Cosine"} for name in names}

    return httpx.Response(200, json={"result": {"config": {"params": {"vectors": vectors}}}})


# --- construction -------------------------------------------------------------------------

@pytest.mark.parametrize("blank", ["", "   "])
def test_empty_base_url_is_refused_at_build_time(blank: str) -> None:
    """QDRANT_URL="" (what compose substitutes for an unset var) → error at construction, not a
    connection error mid-run."""
    with pytest.raises(RetrievalConfigError, match="QDRANT_URL"):
        QdrantClient(base_url=blank, collection=COLLECTION)


@pytest.mark.parametrize("blank", ["", "   "])
def test_empty_collection_is_refused_at_build_time(blank: str) -> None:
    """QDRANT_COLLECTION="" → error at construction; an unnamed collection would write to a path
    that silently means something else."""
    with pytest.raises(RetrievalConfigError, match="QDRANT_COLLECTION"):
        QdrantClient(base_url=BASE_URL, collection=blank)


# --- ensure_collection --------------------------------------------------------------------

async def test_missing_collection_is_created_with_both_named_vectors() -> None:
    """No collection yet → created with `problem` and `sts`, both at the configured size. Building
    only one vector now would make adding the other a full re-index later."""
    seen: list = []
    client     = _client(
        capturing(seen, {("GET", PATH_COLLECTION): httpx.Response(404)})
    )

    created = await client.ensure_collection(vector_size=SIZE)

    assert created is True

    write = next(call for call in seen if call["method"] == "PUT")

    assert write["body"]["vectors"][VECTOR_PROBLEM]["size"] == SIZE
    assert write["body"]["vectors"][VECTOR_STS]["size"]     == SIZE


async def test_created_vectors_use_cosine() -> None:
    """Collection creation → Cosine distance, the metric stage 3 measured on normalised vectors;
    another metric would make RAG_SCORE_MIN mean something the measurement never covered."""
    seen: list = []
    client     = _client(
        capturing(seen, {("GET", PATH_COLLECTION): httpx.Response(404)})
    )

    await client.ensure_collection(vector_size=SIZE)

    write = next(call for call in seen if call["method"] == "PUT")

    assert write["body"]["vectors"][VECTOR_PROBLEM]["distance"] == "Cosine"
    assert write["body"]["vectors"][VECTOR_STS]["distance"]     == "Cosine"


async def test_matching_collection_is_left_alone() -> None:
    """Collection already correct → reported as not created, and nothing is written."""
    seen: list = []
    client     = _client(
        capturing(
            seen,
            {("GET", PATH_COLLECTION): _collection_of(SIZE, (VECTOR_PROBLEM, VECTOR_STS))},
        )
    )

    created = await client.ensure_collection(vector_size=SIZE)

    assert created is False
    assert [call["method"] for call in seen] == ["GET"]


async def test_wrong_vector_size_is_refused_with_both_numbers() -> None:
    """Existing collection built for another model → config error naming BOTH sizes. Adapting
    silently would produce an index nobody can compare against, and the failure would otherwise
    surface as rejected points an hour into a run that already paid for LLM parsing."""
    client = _client(
        routed(
            {("GET", PATH_COLLECTION): _collection_of(1024, (VECTOR_PROBLEM, VECTOR_STS))}
        )
    )

    with pytest.raises(RetrievalConfigError, match="1024") as excinfo:
        await client.ensure_collection(vector_size=SIZE)

    # Both numbers, because one of them alone does not say which side to fix.
    assert "768" in str(excinfo.value)


async def test_missing_named_vector_is_refused() -> None:
    """Collection carrying only `problem` → config error naming the missing vector, not a silent
    write into a collection that cannot hold dedup vectors."""
    client = _client(
        routed(
            {("GET", PATH_COLLECTION): _collection_of(SIZE, (VECTOR_PROBLEM,))}
        )
    )

    with pytest.raises(RetrievalConfigError, match=VECTOR_STS):
        await client.ensure_collection(vector_size=SIZE)


async def test_unrecognised_description_fails_with_our_message() -> None:
    """Collection description of an unexpected shape → our config error, never a KeyError from
    three levels inside the payload."""
    client = _client(
        routed({("GET", PATH_COLLECTION): httpx.Response(200, json={"result": {}})})
    )

    with pytest.raises(RetrievalConfigError, match=COLLECTION):
        await client.ensure_collection(vector_size=SIZE)


# --- upsert -------------------------------------------------------------------------------

async def test_upsert_sends_the_wire_shape_and_waits() -> None:
    """Points in → named vectors on the wire, and `wait=true` so a reported write is a done write
    (an indexing run reports what it wrote and a later step reads it back)."""
    seen: list = []
    client     = _client(capturing(seen))

    written = await client.upsert_points([POINT])

    assert written == 1

    call = seen[0]

    assert call["params"]["wait"]                              == "true"
    assert call["body"]["points"][0]["id"]                     == POINT.point_id
    assert call["body"]["points"][0]["vector"][VECTOR_PROBLEM] == POINT.vector_problem


async def test_upsert_of_nothing_writes_nothing() -> None:
    """Empty list → zero written and no request. A filter rejecting everything is a legitimate
    outcome, and the caller must be able to tell it from a crash."""
    seen: list = []
    client     = _client(capturing(seen))

    assert await client.upsert_points([]) == 0
    assert seen                           == []


async def test_upsert_splits_into_batches() -> None:
    """More points than one batch → several requests, together carrying every point exactly once.
    One giant request would lose a whole run's work to a single failure."""
    seen: list = []
    client     = _client(capturing(seen))
    points     = [POINT.model_copy(update={"point_id": f"id-{index}"}) for index in range(150)]

    written = await client.upsert_points(points)

    assert written    == 150
    assert len(seen)  > 1

    sent = [point["id"] for call in seen for point in call["body"]["points"]]

    assert sent == [f"id-{index}" for index in range(150)]


# --- delete and count ---------------------------------------------------------------------

async def test_delete_reports_whether_anything_was_removed() -> None:
    """Existing collection → deleted and reported True; `index rebuild` prints which happened."""
    client = _client(
        routed(
            {("GET", PATH_COLLECTION): _collection_of(SIZE, (VECTOR_PROBLEM, VECTOR_STS))}
        )
    )

    assert await client.delete_collection() is True


async def test_delete_of_a_missing_collection_is_not_an_error() -> None:
    """No collection → False and no DELETE. An absent collection is a normal starting state for a
    rebuild, not a failure."""
    seen: list = []
    client     = _client(
        capturing(seen, {("GET", PATH_COLLECTION): httpx.Response(404)})
    )

    assert await client.delete_collection() is False
    assert [call["method"] for call in seen] == ["GET"]


async def test_count_asks_for_an_exact_number() -> None:
    """count_points() → exact:true on the wire; an approximate count would make the "two rebuilds
    give the same state" assertion flaky."""
    seen: list = []
    client     = _client(
        capturing(
            seen,
            {
                ("POST", f"{PATH_POINTS}/count"): httpx.Response(
                    200, json={"result": {"count": 200}}
                )
            },
        )
    )

    assert await client.count_points() == 200
    assert seen[0]["body"]["exact"] is True


# --- search -------------------------------------------------------------------------------

def _hits(*entries: dict) -> httpx.Response:
    """
    Description:
    Builds the answer Qdrant returns from a query, wrapping entries in the nesting the query
    endpoint uses. Spelled once because every search test needs it and the nesting is the part
    easiest to get subtly wrong.

    Example args:
        entries=({"id": "3f2a…", "score": 0.87, "payload": {"ticket_id": "33644"}},)

    Example result:
        httpx.Response(200, json={"result": {"points": [{…}]}})
    """
    return httpx.Response(200, json={"result": {"points": list(entries)}})


async def test_search_asks_the_named_space_it_was_given() -> None:
    """search(vector_name=VECTOR_PROBLEM) → "using": "problem" on the wire. The collection holds
    two spaces and querying the wrong one returns plausible nonsense rather than an error, so the
    name must travel exactly as passed."""
    seen: list = []
    client     = _client(
        capturing(seen, {("POST", f"{PATH_POINTS}/query"): _hits()})
    )

    await client.search(vector=[0.1, -0.2], vector_name=VECTOR_PROBLEM, limit=5)

    assert seen[0]["body"]["using"] == VECTOR_PROBLEM
    assert seen[0]["body"]["query"] == [0.1, -0.2]
    assert seen[0]["body"]["limit"] == 5


async def test_search_asks_for_payloads() -> None:
    """search() → with_payload:true, because every caller builds on payload fields; ids and scores
    alone would make the generation prompt impossible to fill."""
    seen: list = []
    client     = _client(
        capturing(seen, {("POST", f"{PATH_POINTS}/query"): _hits()})
    )

    await client.search(vector=[0.1], vector_name=VECTOR_STS, limit=1)

    assert seen[0]["body"]["with_payload"] is True
    # The other space, passed through just as faithfully — this is the mistake that stays silent.
    assert seen[0]["body"]["using"] == VECTOR_STS


async def test_search_returns_hits_in_the_order_qdrant_gave_them() -> None:
    """A query answer → TicketHits carrying score, point id and payload, order preserved: the
    threshold and the collapsing downstream both read best-first."""
    client = _client(
        routed(
            {
                ("POST", f"{PATH_POINTS}/query"): _hits(
                    {"id": "a", "score": 0.91, "payload": {"ticket_id": "33644"}},
                    {"id": "b", "score": 0.42, "payload": {"ticket_id": "10718"}},
                )
            }
        )
    )

    hits = await client.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5)

    assert [hit.ticket_id for hit in hits] == ["33644", "10718"]
    assert [hit.score for hit in hits]     == [0.91, 0.42]
    assert hits[0].point_id                == "a"


async def test_search_finding_nothing_is_an_answer() -> None:
    """An empty result → an empty list, not an error. A query matching nothing is the documented
    "new kind of problem" case, which the product reports rather than treats as a failure."""
    client = _client(routed({("POST", f"{PATH_POINTS}/query"): _hits()}))

    assert await client.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5) == []


async def test_search_of_an_unknown_named_vector_fails_loudly() -> None:
    """Qdrant rejects an unknown vector name → RetrievalError carrying its explanation, never an
    empty list: a silent [] here reads as "nothing similar found" and hides a wiring mistake."""
    client = _client(
        routed(
            {
                ("POST", f"{PATH_POINTS}/query"): httpx.Response(
                    400, text="Wrong input: Vector name error: vector 'problme' does not exist"
                )
            }
        )
    )

    with pytest.raises(RetrievalError, match="does not exist"):
        await client.search(vector=[0.1], vector_name="problme", limit=5)


async def test_search_with_an_unrecognised_body_fails_with_our_message() -> None:
    """A 200 whose shape we do not recognise → RetrievalError naming the collection, rather than a
    KeyError surfacing later inside the search service."""
    client = _client(
        routed({("POST", f"{PATH_POINTS}/query"): httpx.Response(200, json={"result": {}})})
    )

    with pytest.raises(RetrievalError, match=COLLECTION):
        await client.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5)


# --- transport failures -------------------------------------------------------------------

async def test_unreachable_qdrant_becomes_a_retrieval_error() -> None:
    """Connection refused → RetrievalError, never an httpx type: the transport must not leak into
    the domain (rule 4)."""
    client = _client(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(RetrievalError):
        await client.ensure_collection(vector_size=SIZE)


async def test_timeout_becomes_a_retrieval_error() -> None:
    """Qdrant does not answer in time → RetrievalError naming the collection."""
    client = _client(raising(httpx.TimeoutException("timed out")))

    with pytest.raises(RetrievalError, match=COLLECTION):
        await client.ensure_collection(vector_size=SIZE)


async def test_rejected_upsert_carries_qdrants_explanation() -> None:
    """Qdrant rejects a write (wrong vector size, unknown vector name) → the error carries its
    reason. That text is ours, not the customer's, and it is the only thing that says WHY."""
    client = _client(
        routed(
            {
                ("PUT", PATH_POINTS): httpx.Response(
                    400, text="Wrong input: Vector dimension error"
                )
            }
        )
    )

    with pytest.raises(RetrievalError, match="Vector dimension error"):
        await client.upsert_points([POINT])


async def test_non_json_body_becomes_a_retrieval_error() -> None:
    """A 200 whose body is not JSON (a proxy error page, typically) → RetrievalError rather than a
    decoding crash far from the cause."""
    client = _client(
        routed({("GET", PATH_COLLECTION): httpx.Response(200, text="<html>")})
    )

    with pytest.raises(RetrievalError):
        await client.ensure_collection(vector_size=SIZE)
