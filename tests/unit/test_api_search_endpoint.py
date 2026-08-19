from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.factory import get_searcher
from app.main import create_app
from app.model.rag_search_result import SearchResult
from app.model.ticket_parsed import ParsedTicket
from app.model.ticket_raw import RawTicket
from app.retrieval import TicketHit
from app.service.rag_searcher import SearchParseError

# The HTTP CONTRACT of POST /search, proved in-process: status codes, request validation, payload
# shape. That the route is actually mounted in the built image belongs to `integration_api` — the
# same split `/health` already follows (CLAUDE.md -> "Testy": contract in-process, deployment over
# HTTP).

PARSED_FIELDS = {
    "ticket_id":                     "41002",
    "date":                          "2026-08-19",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "brak",
    "solution":                      "brak",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}

HIT_PAYLOAD = {
    "ticket_id":         "33644",
    "date":              "2026-03-14",
    "component":         "ePUAP",
    "problem":           "Wysyłka kończy się błędem komunikacji",
    "symptoms":          "Komunikat o braku połączenia",
    "cause":             "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":          "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":        "naprawione",
    "questions_summary": "pytano o wersję przeglądarki",
}


class FakeSearcher:
    """
    Description:
    Stands in for `RagSearcher`, returning a prepared result and recording the ticket it was asked
    about — or raising, when a test is about the failure path.

    A stub rather than the real service on fakes: this file tests the HTTP contract, and driving
    that through a real searcher would make every assertion depend on the parser and the threshold
    as well.
    """

    def __init__(
        self,
        result: SearchResult | None = None,
        error:  Exception | None    = None,
    ) -> None:
        """
        Description:
        Builds the stub with either the result it will return or the error it will raise.

        Example args:
            result=SearchResult(query=ParsedTicket(…), hits=[])

        Example result:
            FakeSearcher recording into `seen`
        """
        self._result = result
        self._error  = error
        self.seen: list[RawTicket] = []

    async def search(self, raw: RawTicket) -> SearchResult:
        """
        Description:
        Records the ticket and returns the prepared result, or raises the prepared error.

        Example args:
            raw=RawTicket(ticket_id="41002", …)

        Example result:
            SearchResult(query=ParsedTicket(…), hits=[TicketHit(…)])

        Raises:
            Exception: whatever the stub was built with
        """
        self.seen.append(raw)

        if self._error is not None:
            raise self._error

        assert self._result is not None

        return self._result


def _result(
    hits:    list[TicketHit] | None = None,
    dropped: int                    = 0,
) -> SearchResult:
    """
    Description:
    Builds a search result over the shared parsed query, so tests state only what they are about.

    Example args:
        hits=[TicketHit(point_id="p-33644", score=0.87, payload={…})]
        dropped=2

    Example result:
        SearchResult(query=ParsedTicket(…), hits=[…], dropped_below_threshold=2)
    """
    return SearchResult(
        query                   = ParsedTicket.model_validate(PARSED_FIELDS),
        hits                    = hits or [],
        dropped_below_threshold = dropped,
    )


def _client(searcher: FakeSearcher) -> TestClient:
    """
    Description:
    Builds a client over the real application with the searcher dependency replaced.

    Overriding the dependency rather than patching a module attribute: that is the seam FastAPI
    provides, and it leaves the router, the middleware and the exception handlers exactly as they
    run in production — which is what this file exercises.

    Example args:
        searcher=FakeSearcher(result=_result())

    Example result:
        TestClient answering POST /search from the stub
    """
    app = create_app()
    app.dependency_overrides[get_searcher] = lambda: searcher

    return TestClient(app)


@pytest.fixture
def client_with_hit() -> TestClient:
    """
    Description:
    A client whose search returns exactly one hit — the ordinary case.

    Example args:
        (none)

    Example result:
        TestClient returning one hit for every POST /search
    """
    hit = TicketHit(point_id="p-33644", score=0.87, payload=HIT_PAYLOAD)

    return _client(FakeSearcher(result=_result(hits=[hit])))


# --- the contract ---------------------------------------------------------------------------

def test_a_minimal_request_is_enough(client_with_hit: TestClient) -> None:
    """ticket_id + body → 200. Everything else is optional on purpose: the rest describes the
    ticket without steering the search, so demanding it would only raise the integration cost."""
    response = client_with_hit.post(
        "/search", json={"ticket_id": "41002", "body": "Nie mogę wysłać pisma przez ePUAP."}
    )

    assert response.status_code == 200


def test_a_hit_carries_the_fields_an_answer_is_built_from(client_with_hit: TestClient) -> None:
    """A hit → score, id, date and the content fields. `date` is unconditional because staleness,
    contradictions between records and seasonality all depend on it."""
    response = client_with_hit.post(
        "/search", json={"ticket_id": "41002", "body": "Nie mogę wysłać pisma."}
    )
    hit = response.json()["hits"][0]

    assert hit["ticket_id"] == "33644"
    assert hit["score"]     == 0.87
    assert hit["date"]      == "2026-03-14"
    assert hit["solution"]  == HIT_PAYLOAD["solution"]
    assert hit["cause"]     == HIT_PAYLOAD["cause"]


def test_the_whole_parsed_query_comes_back(client_with_hit: TestClient) -> None:
    """The response carries the FULL reading of the ticket, not just the embedded half: a misread
    `component` or a dropped error code is invisible in `problem` alone and would only surface as
    a strange proposal in stage 6."""
    response = client_with_hit.post(
        "/search", json={"ticket_id": "41002", "body": "Nie mogę wysłać pisma."}
    )
    query = response.json()["query"]

    assert query["problem"]     == PARSED_FIELDS["problem"]
    assert query["symptoms"]    == PARSED_FIELDS["symptoms"]
    assert query["component"]   == "ePUAP"
    assert query["error_codes"] == ["ERR-4210"]
    assert query["resolution"]  == "naprawione"


def test_optional_fields_reach_the_domain_model() -> None:
    """subject, category and comments travel through to the ticket the searcher parses — the
    thread is what the prompt reads, and a comment dropped on the way in is context lost."""
    searcher = FakeSearcher(result=_result())
    client   = _client(searcher)

    client.post(
        "/search",
        json={
            "ticket_id": "41002",
            "body":      "Nie mogę wysłać pisma.",
            "subject":   "Błąd wysyłki",
            "category":  "Automat mailowy",
            "comments":  [{"body": "Sprawdziłem uprawnienia.", "role": "konsultant"}],
        },
    )
    raw = searcher.seen[0]

    assert raw.subject          == "Błąd wysyłki"
    assert raw.category         == "Automat mailowy"
    assert raw.comments[0].body == "Sprawdziłem uprawnienia."
    assert raw.comments[0].role == "konsultant"


def test_a_missing_date_becomes_today() -> None:
    """No date → today. A ticket being searched with is current by definition, and the date does
    not reach the vector — demanding it would be asking for a field we do not use."""
    searcher = FakeSearcher(result=_result())
    client   = _client(searcher)

    client.post("/search", json={"ticket_id": "41002", "body": "Nie mogę wysłać pisma."})

    assert searcher.seen[0].date == date.today()


def test_an_unlabelled_comment_is_accepted() -> None:
    """A comment with only a body → accepted, with a placeholder role. Labels are deliberately not
    trusted in this corpus (the author is inverted in one whole category), so a missing one makes
    the input thinner, never invalid."""
    searcher = FakeSearcher(result=_result())
    client   = _client(searcher)

    response = client.post(
        "/search",
        json={
            "ticket_id": "41002",
            "body":      "Nie mogę wysłać pisma.",
            "comments":  [{"body": "Bez etykiety."}],
        },
    )

    assert response.status_code               == 200
    assert searcher.seen[0].comments[0].role  != ""


# --- empty results are answers, not failures ------------------------------------------------

def test_finding_nothing_is_a_200_with_an_empty_list() -> None:
    """No hits → 200 and an empty list, never a 404. "New kind of problem" is a correct and
    frequent answer here (47% of the corpus are singletons); a 404 would claim the REQUEST was
    wrong."""
    client = _client(FakeSearcher(result=_result()))

    response = client.post("/search", json={"ticket_id": "41002", "body": "Coś nowego."})

    assert response.status_code    == 200
    assert response.json()["hits"] == []


def test_the_threshold_count_is_reported() -> None:
    """Hits cut by the threshold → reported as a count. Without it a strict threshold looks
    exactly like an empty index, and those are different diagnoses."""
    client = _client(FakeSearcher(result=_result(dropped=3)))

    response = client.post("/search", json={"ticket_id": "41002", "body": "Coś nowego."})

    assert response.json()["dropped_below_threshold"] == 3


# --- failure paths --------------------------------------------------------------------------

def test_a_request_without_a_body_is_refused() -> None:
    """Missing `body` → 422 in the uniform error shape. The body IS the query, so a request
    without it is malformed rather than a search that found nothing."""
    client = _client(FakeSearcher(result=_result()))

    response = client.post("/search", json={"ticket_id": "41002"})

    assert response.status_code == 422
    assert "detail" in response.json()


def test_an_unparseable_ticket_is_a_422() -> None:
    """The model's answer did not validate → 422, not 503: that is a statement about the INPUT,
    unlike an unreachable dependency, and the caller must not be told to retry."""
    client = _client(
        FakeSearcher(error=SearchParseError("nie udało się sparsować zgłoszenia 41002"))
    )

    response = client.post("/search", json={"ticket_id": "41002", "body": "…"})

    assert response.status_code == 422
    assert "41002" in response.json()["detail"]


def test_the_response_carries_a_request_id(client_with_hit: TestClient) -> None:
    """Every answer carries the correlation header, so one id stitches together the log lines of a
    search that spans the parser, the embedder and Qdrant."""
    response = client_with_hit.post(
        "/search", json={"ticket_id": "41002", "body": "Nie mogę wysłać pisma."}
    )

    assert response.headers["X-Request-ID"]
