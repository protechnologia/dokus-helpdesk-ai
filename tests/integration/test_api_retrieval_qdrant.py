import math
import os
from collections.abc import Iterator

import pytest

from app.retrieval import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    QdrantClient,
    RetrievalConfigError,
    RetrievalError,
    TicketPoint,
    point_id_for,
)

pytestmark = [pytest.mark.integration, pytest.mark.integration_qdrant]

# What lives OUTSIDE our code and is therefore worth a running service: that Qdrant really accepts
# a two-named-vector collection, really stores a payload alongside the vectors, really returns the
# point under the id we derived, and really reports a size mismatch instead of adapting. Everything
# we can prove ourselves — the wire shape, batching, error translation — is covered in-process by
# tests/unit and repeating it here would only lengthen a run that needs the stack.
#
# The stack assumption from CLAUDE.md -> "Testy" applies: an unreachable Qdrant fails these tests,
# it never skips them. Asking for this marker means the service is supposed to be up.

# Integration tests run on the HOST, so they reach Qdrant through its published port — never
# through the compose-internal QDRANT_URL (`http://qdrant:6333`), which resolves only inside the
# compose network. Hence a test-only variable with a host default.
QDRANT_URL_ENV     = "QDRANT_TEST_URL"
QDRANT_URL_DEFAULT = "http://localhost:6333"

# Its own collection, never the configured one: these tests create and DELETE what they touch, and
# doing that to `tickets` would wipe a real index during a routine test run.
TEST_COLLECTION = "tickets_integration_test"

# Small enough to write out, and deliberately NOT the production 768: nothing here depends on the
# real dimension, and a small one keeps the payloads readable.
SIZE = 4


def _ticket_point(
    ticket_id: str,          # e.g. "33644"
    fill:      float = 0.1,  # every component of the `problem` vector
) -> TicketPoint:
    """
    Description:
    Builds one point with recognisable vectors and a payload carrying the fields an answer is
    generated from. Constructed directly rather than through ParsedTicket: this file tests
    storage, and going through the domain model would tie it to schema changes.

    Example args:
        ticket_id="33644"
        fill=0.1

    Example result:
        TicketPoint(point_id="df3b51f3-…", payload={"ticket_id": "33644", …})
    """
    return TicketPoint(
        point_id       = point_id_for(ticket_id),
        vector_problem = [fill] * SIZE,
        # A different value, so a swapped pair of named vectors is visible on read-back.
        vector_sts     = [-fill] * SIZE,
        payload        = {
            "ticket_id": ticket_id,
            "date":      "2026-03-14",
            "component": "ePUAP",
            "problem":   "Wysyłka przez ePUAP kończy się błędem komunikacji",
            "cause":     "Certyfikat bez uprawnienia AddDocumentToSign",
            "solution":  "Wygenerowano certyfikat z właściwym uprawnieniem.",
        },
    )


def _cosine(
    first:  list[float],  # e.g. [0.5, 0.5, 0.5, 0.5] — as read back from Qdrant
    second: list[float],  # e.g. [0.1, 0.1, 0.1, 0.1] — as written
) -> float:
    """
    Description:
    Cosine similarity of two vectors, used to compare a stored vector with the written one by
    DIRECTION. Needed because a Cosine collection re-normalises on write, so equality would fail
    on a correctly stored vector.

    Example args:
        first=[0.5, 0.5, 0.5, 0.5]
        second=[0.1, 0.1, 0.1, 0.1]

    Example result:
        1.0
    """
    dot   = sum(a * b for a, b in zip(first, second, strict=True))
    norms = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))

    return dot / norms


@pytest.fixture
async def client() -> Iterator[QdrantClient]:
    """
    Description:
    Yields a client bound to the running Qdrant, on a throwaway collection dropped before and
    after each test. Dropping BEFORE as well as after matters: a test killed halfway would
    otherwise leave a collection that makes the next run assert against stale state.

    Example args:
        (none)

    Example result:
        QdrantClient(collection="tickets_integration_test")
    """
    base_url = os.environ.get(QDRANT_URL_ENV, QDRANT_URL_DEFAULT)
    client   = QdrantClient(base_url=base_url, collection=TEST_COLLECTION, timeout=10.0)

    await client.delete_collection()

    yield client

    await client.delete_collection()
    await client.aclose()


async def test_collection_is_created_with_both_named_vectors(client: QdrantClient) -> None:
    """Fresh collection → Qdrant really accepts two named vectors at the configured size, and
    verifying the same collection again reports "already there" rather than rewriting it."""
    assert await client.ensure_collection(vector_size=SIZE) is True

    # Second call proves the verification path against a REAL description, which is the half our
    # unit tests can only assert against a payload we wrote ourselves.
    assert await client.ensure_collection(vector_size=SIZE) is False


async def test_point_returns_with_its_payload_and_both_vectors(client: QdrantClient) -> None:
    """Upserted point → readable back under the id we derived, with the payload intact and each
    named vector in its own slot. This is the whole contract stage 4 rests on."""
    await client.ensure_collection(vector_size=SIZE)

    point = _ticket_point("33644")

    assert await client.upsert_points([point]) == 1

    stored = await client._request(
        "POST",
        f"/collections/{TEST_COLLECTION}/points",
        json={"ids": [point.point_id], "with_payload": True, "with_vector": True},
    )
    result = stored["result"][0]

    assert result["payload"]["ticket_id"] == "33644"
    # `solution` travels in the payload rather than in the vector — retrieval reads it to build an
    # answer, so losing it would leave hits that match but say nothing.
    assert result["payload"]["solution"]  == point.payload["solution"]

    # Compared by DIRECTION, not component by component: a Cosine collection re-normalises vectors
    # on write, so [0.1]*4 comes back as [0.5]*4. Discovered here rather than assumed — exactly the
    # kind of truth that lives outside our code. It costs us nothing (the embedder already returns
    # unit vectors, and cosine ignores length by definition), but an equality assertion would fail
    # for a system behaving correctly.
    assert _cosine(result["vector"][VECTOR_PROBLEM], point.vector_problem) == pytest.approx(1.0)
    # The `sts` vector points the OPPOSITE way here, so this also proves the two named vectors did
    # not get swapped — a mix-up that is invisible later, because both slots still hold valid
    # numbers while queries and dedup silently search each other's space.
    assert _cosine(result["vector"][VECTOR_STS], point.vector_sts) == pytest.approx(1.0)


async def test_reupserting_the_same_ticket_overwrites_it(client: QdrantClient) -> None:
    """Same ticket written twice → one point, not two. This is what makes `index rebuild`
    idempotent; without it a rebuild would duplicate the corpus instead of replacing it."""
    await client.ensure_collection(vector_size=SIZE)

    await client.upsert_points([_ticket_point("33644", fill=0.1)])
    await client.upsert_points([_ticket_point("33644", fill=0.9)])

    assert await client.count_points() == 1


async def test_wrong_vector_size_is_refused_against_a_real_collection(client: QdrantClient) -> None:
    """Collection built at one size, configuration says another → config error rather than a
    write into a collection whose vectors mean something else. Checked against a REAL Qdrant
    description, because the shape of that description is not ours to define."""
    await client.ensure_collection(vector_size=SIZE)

    with pytest.raises(RetrievalConfigError):
        await client.ensure_collection(vector_size=SIZE + 1)


async def test_search_ranks_the_nearest_point_first(client: QdrantClient) -> None:
    """Query vector → hits ordered by real similarity, carrying payload and score. Sorting is
    Qdrant's job, not ours, so this is the half no in-process test can prove."""
    await client.ensure_collection(vector_size=SIZE)

    # Two points pointing in different directions, so "nearest" is decided by the data rather than
    # by insertion order — which is what makes the ranking assertion mean anything.
    near = _ticket_point("33644", fill=0.1)
    far  = TicketPoint(
        point_id       = point_id_for("10718"),
        vector_problem = [0.1, 0.1, -0.1, -0.1],
        vector_sts     = [0.2] * SIZE,
        payload        = {"ticket_id": "10718"},
    )

    await client.upsert_points([near, far])

    hits = await client.search(
        vector      = near.vector_problem,
        vector_name = VECTOR_PROBLEM,
        limit       = 5,
    )

    assert [hit.ticket_id for hit in hits] == ["33644", "10718"]
    # The payload has to survive the round trip: an answer is generated from these fields, so a hit
    # without them matches but says nothing.
    assert hits[0].payload["solution"] == near.payload["solution"]
    assert hits[0].score > hits[1].score


async def test_search_reads_the_named_space_it_was_asked_for(client: QdrantClient) -> None:
    """Same vector queried against `problem` and against `sts` → different scores. This is the
    mistake that never announces itself: both spaces answer, and the wrong one returns
    plausible-looking hits (measured: 96.7% vs 98.3% recall@1, a drop rather than a failure)."""
    await client.ensure_collection(vector_size=SIZE)

    # `sts` deliberately points the opposite way to `problem` (see `_ticket_point`), so querying
    # the wrong space is visible as a sign flip rather than as a subtle difference.
    point = _ticket_point("33644")

    await client.upsert_points([point])

    on_problem = await client.search(
        vector=point.vector_problem, vector_name=VECTOR_PROBLEM, limit=1
    )
    on_sts     = await client.search(
        vector=point.vector_problem, vector_name=VECTOR_STS, limit=1
    )

    assert on_problem[0].score == pytest.approx(1.0)
    # Same query, same point, other space — and the score is as far from 1.0 as it gets. Nothing
    # errors, which is precisely why the vector name is a required argument.
    assert on_sts[0].score == pytest.approx(-1.0)


async def test_search_of_an_unknown_named_vector_is_an_error(client: QdrantClient) -> None:
    """Misspelled vector name → RetrievalError from a REAL Qdrant, never an empty list. An empty
    list would read as "nothing similar in the corpus" and hide the wiring mistake for good."""
    await client.ensure_collection(vector_size=SIZE)
    await client.upsert_points([_ticket_point("33644")])

    with pytest.raises(RetrievalError):
        await client.search(vector=[0.1] * SIZE, vector_name="problme", limit=5)


async def test_deleting_removes_the_collection(client: QdrantClient) -> None:
    """Collection dropped → really gone, and dropping again reports "nothing to remove". The
    index is a derivative rebuildable from data/parsed/ (rule 8), so this is an ordinary
    operation."""
    await client.ensure_collection(vector_size=SIZE)

    assert await client.delete_collection() is True
    assert await client.delete_collection() is False
