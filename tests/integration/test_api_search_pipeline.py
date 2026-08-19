import json
import os
from collections.abc import AsyncIterator
from datetime import date

import pytest

from app.embedding import EmbeddingClient
from app.llm.client_fake import FakeLLMClient
from app.model.ticket_raw import RawTicket
from app.retrieval import QdrantClient
from app.service.parser_ticket_parsed import TicketParser
from app.service.rag_searcher import RagSearcher
from tests.conftest import embedder_url, qdrant_url

pytestmark = [pytest.mark.integration, pytest.mark.integration_api]

# The one path nothing else covers: `api` talking to the embedder AND Qdrant in the same run.
# Every other integration test touches a single dependency, so a query vector that is not
# comparable with the indexed ones would pass every one of them — both sides keep returning
# well-formed vectors and Qdrant keeps returning scored hits (CLAUDE.md -> "Embeddingi": a prefix
# mix-up costs a few points of recall and never raises).
#
# The LLM is a scripted fake here, on purpose. That makes this an INTEGRATION test rather than a
# functional one: the input is a ParsedTicket we supply, not a real ticket the model read, so what
# is proved is the wiring — not that the product behaves sensibly. The functional half lives in
# `test_api_search_functional.py` and needs a live model.

# The real collection, read-only. Nothing here writes or deletes, so pointing at the working index
# is safe — and it is the only way to assert against records the product actually serves.
COLLECTION = os.environ.get("QDRANT_TEST_COLLECTION", "tickets")

VECTOR_SIZE = 768

# Enough of a parsed ticket to build the embedding text; the rest is filled with the schema's
# explicit "no value" so the artifact validates without inventing content.
NO_VALUE = "brak"


def _scripted_parse(
    problem:  str,  # e.g. "Brak wizualizacji UPD w dokumencie XML"
    symptoms: str,  # e.g. "W dokumencie wychodzącym brakuje wizualizacji pliku XML."
) -> str:
    """
    Description:
    Builds the JSON answer the fake model returns, so the searcher parses a ticket we chose.

    Only `problem` and `symptoms` carry meaning: they are the two embedded fields, and this test
    is about whether the vector built from them finds the matching record.

    Example args:
        problem="Brak wizualizacji UPD w dokumencie XML"
        symptoms="W dokumencie wychodzącym brakuje wizualizacji pliku XML."

    Example result:
        '{"component": "brak", "problem": "Brak wizualizacji UPD…", …}'
    """
    return json.dumps(
        {
            "component":         NO_VALUE,
            "problem":           problem,
            "symptoms":          symptoms,
            "error_codes":       [],
            "cause":             NO_VALUE,
            "solution":          NO_VALUE,
            "resolution":        NO_VALUE,
            "questions_summary": NO_VALUE,
        },
        ensure_ascii = False,
    )


@pytest.fixture
async def qdrant() -> AsyncIterator[QdrantClient]:
    """
    Description:
    Yields a Qdrant client bound to the running service and the real collection.

    Example args:
        (none)

    Example result:
        QdrantClient(collection="tickets")
    """
    client = QdrantClient(
        base_url   = qdrant_url(),
        collection = COLLECTION,
        timeout    = 30.0,
    )

    yield client

    await client.aclose()


@pytest.fixture
async def indexed_record(qdrant: QdrantClient) -> dict:
    """
    Description:
    Reads one real record out of the collection and hands back its payload, so the test asserts
    against a ticket the product actually serves rather than one it planted.

    Fails loudly on an empty collection instead of skipping: these tests are behind a marker, so
    asking for them means the index is supposed to be built (CLAUDE.md -> "Testy").

    Example args:
        (none)

    Example result:
        {"ticket_id": "12617", "problem": "Brak wizualizacji UPD…", …}

    Raises:
        AssertionError: the collection is empty — run `helpdesk rag index` first
    """
    points = await qdrant._request(
        "POST",
        f"/collections/{COLLECTION}/points/scroll",
        json={"limit": 1, "with_payload": True, "with_vector": False},
    )
    found = points["result"]["points"]

    assert found, (
        f"kolekcja '{COLLECTION}' jest pusta — zbuduj indeks "
        f"(`helpdesk rag index data/parsed/bielik-11b-golden200`) przed tym testem"
    )

    return found[0]["payload"]


@pytest.fixture
async def searcher_for(indexed_record: dict) -> AsyncIterator[RagSearcher]:
    """
    Description:
    Yields a searcher wired to the REAL embedder and Qdrant, with the model scripted to return the
    chosen record's own `problem` and `symptoms`.

    Scripting the model that way turns the test into the sharpest possible check of the wiring: if
    the query vector is built the same way the indexed ones were, a record asked for with its own
    text must come back first. If the two sides drifted apart — a different mode, a different way
    of assembling the text — it would not.

    Example args:
        indexed_record={"ticket_id": "12617", "problem": "…", "symptoms": "…"}

    Example result:
        RagSearcher over the live embedder and the real collection
    """
    embedder = EmbeddingClient(
        base_url = embedder_url(),
        timeout  = 120.0,
    )
    qdrant = QdrantClient(
        base_url   = qdrant_url(),
        collection = COLLECTION,
        timeout    = 30.0,
    )
    llm = FakeLLMClient(
        responses=[
            _scripted_parse(
                problem  = indexed_record["problem"],
                symptoms = indexed_record["symptoms"],
            )
        ]
    )
    searcher = RagSearcher(
        parser    = TicketParser(llm=llm),
        embedder  = embedder,
        qdrant    = qdrant,
        top_k     = 5,
        # Nothing is cut: this test is about whether the right record ranks first, and a threshold
        # would turn a ranking failure into an empty list, hiding which of the two went wrong.
        score_min = 0.0,
    )

    yield searcher

    await searcher.aclose()


def _raw(text: str) -> RawTicket:
    """
    Description:
    Builds the incoming ticket handed to the searcher. Its content does not reach the vector — the
    model is scripted — but the pipeline requires a well-formed thread to parse.

    Example args:
        text="Nie działa wizualizacja dokumentu."

    Example result:
        RawTicket(ticket_id="pipeline-test", date=date.today(), body="Nie działa wizualizacja…")
    """
    return RawTicket(
        ticket_id = "pipeline-test",
        date      = date.today(),
        category  = "",
        subject   = "",
        body      = text,
    )


async def test_a_record_asked_for_with_its_own_text_comes_back_first(
    searcher_for:   RagSearcher,
    indexed_record: dict,
) -> None:
    """Query built from a record's own problem+symptoms → that record ranks first, with a score
    near 1.0. Proves the query vector is comparable with the indexed ones: same model, same mode
    pairing (query→passage), same text assembly. A drift on any of those keeps every component
    working and only degrades the ranking, which is why nothing but this test would catch it."""
    result = await searcher_for.search(_raw("Treść nieistotna — model jest atrapą."))

    assert result.hits, "brak trafień dla rekordu zapytanego jego własnym tekstem"
    assert result.hits[0].ticket_id == indexed_record["ticket_id"]
    # Asserted RELATIVELY, never against an absolute score. The two sides are embedded in
    # different modes — the query carries `[query]: `, the indexed side no prefix — so even
    # identical text lands well below 1.0 (measured here: 0.75, and 0.544 for unrelated texts).
    # An absolute bar would be a number to re-tune on every model change while proving nothing;
    # what this test is about is RANKING, and ranking is the property that survives (a swapped
    # prefix costs a few points of recall, not a failure).
    assert result.hits[0].score > result.hits[1].score


async def test_hits_carry_the_payload_an_answer_needs(searcher_for: RagSearcher) -> None:
    """Hits come back with the fields generation reads — `solution`, `cause`, `date`. The vector
    holds none of them, so this proves the payload survives the round trip through the real
    collection, not just through a stub."""
    result = await searcher_for.search(_raw("Treść nieistotna — model jest atrapą."))
    payload = result.hits[0].payload

    assert payload["ticket_id"]
    assert payload["date"]
    # Present as keys even when the record has no cause: "brak" is an answer, "" would be a field
    # that never made it into the index.
    assert "solution" in payload
    assert "cause"    in payload


async def test_the_query_is_parsed_before_it_is_embedded(searcher_for: RagSearcher) -> None:
    """The result carries the parsed query, which is what was embedded — not the raw text. A raw
    mail carries greetings and signatures that pollute the vector, so this ordering is the reason
    the runtime pays for one extra LLM call."""
    raw    = _raw("Dzień dobry, nie działa wizualizacja. Pozdrawiam, Jan Kowalski")
    result = await searcher_for.search(raw)

    assert result.query.problem
    assert result.query.problem != raw.body
