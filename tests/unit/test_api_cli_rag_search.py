import pytest
from typer.testing import CliRunner

from app.cli.cli import cli
from app.embedding import EmbeddingError
from app.model.rag_search_result import SearchResult
from app.model.ticket_parsed import ParsedTicket
from app.retrieval import TicketHit
from app.service.rag_searcher import SearchParseError

runner = CliRunner()

PARSED_FIELDS = {
    "ticket_id":                     "cli",
    "date":                          "2026-08-19",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   [],
    "cause":                         "brak",
    "solution":                      "brak",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}

HIT_PAYLOAD = {
    "ticket_id": "33644",
    "date":      "2026-03-14",
    "problem":   "Wysyłka kończy się błędem komunikacji",
    "cause":     "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":  "Wygenerowano certyfikat z właściwym uprawnieniem.",
}


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


def _hit(score: float = 0.87) -> TicketHit:
    """
    Description:
    Builds one hit carrying the fields the command prints.

    Example args:
        score=0.87

    Example result:
        TicketHit(point_id="p-33644", score=0.87, payload={"ticket_id": "33644", …})
    """
    return TicketHit(point_id="p-33644", score=score, payload=HIT_PAYLOAD)


class StubSearch:
    """
    Description:
    Stands in for the CLI's search pass, recording the text it was asked about and returning a
    prepared result — or raising, when a test is about the failure path.

    Replaces `_run_search` rather than the service inside it: that keeps the whole command under
    test (argument parsing, printing, exit codes) while the clients, the LLM and Qdrant stay out
    of a unit run.
    """

    def __init__(self) -> None:
        """
        Description:
        Builds the stub with an empty result and no error.

        Example args:
            (none)

        Example result:
            StubSearch returning an empty result, recording into `calls`
        """
        self.calls:  list[str]        = []
        self.result: SearchResult     = _result()
        self.error:  Exception | None = None

    async def __call__(self, text: str) -> SearchResult:
        """
        Description:
        Records the query and either raises the configured error or returns the result.

        Example args:
            text="Nie mogę wysłać pisma przez ePUAP"

        Example result:
            SearchResult(query=ParsedTicket(…), hits=[])

        Raises:
            Exception: whatever the test assigned to `error`
        """
        self.calls.append(text)

        if self.error is not None:
            raise self.error

        return self.result


@pytest.fixture
def stub_search(monkeypatch: pytest.MonkeyPatch) -> StubSearch:
    """
    Description:
    Installs `StubSearch` in place of the CLI's search pass and hands it to the test.

    Example args:
        (none)

    Example result:
        StubSearch whose `calls` fill up as commands run
    """
    stub = StubSearch()

    monkeypatch.setattr("app.cli.rag._run_search", stub)

    return stub


# --- the ordinary case ----------------------------------------------------------------------

def test_the_query_reaches_the_service(stub_search: StubSearch) -> None:
    """The argument travels to the search pass unchanged — the command is a thin adapter and must
    not reshape what the operator typed."""
    result = runner.invoke(cli, ["rag", "search", "Nie mogę wysłać pisma przez ePUAP"])

    assert result.exit_code   == 0
    assert stub_search.calls  == ["Nie mogę wysłać pisma przez ePUAP"]


def test_hits_are_printed_with_score_and_solution(stub_search: StubSearch) -> None:
    """Hits → id, score and the fields an answer is built from. `solution` is the reason anyone
    runs this at all, so it has to be on screen rather than a field away."""
    stub_search.result = _result(hits=[_hit(score=0.87)])

    result = runner.invoke(cli, ["rag", "search", "Błąd wysyłki"])

    assert "33644" in result.stdout
    assert "0.870" in result.stdout
    assert "Wygenerowano certyfikat" in result.stdout


def test_the_parsed_query_is_printed(stub_search: StubSearch) -> None:
    """How the model read the ticket is printed unconditionally: a surprising hit list is
    explained by an unexpected reading far more often than by the search, and on a terminal that
    reading is otherwise invisible."""
    stub_search.result = _result(hits=[_hit()])

    result = runner.invoke(cli, ["rag", "search", "Błąd wysyłki"])

    assert PARSED_FIELDS["problem"] in result.stdout
    assert "ePUAP" in result.stdout


# --- empty results are answers ---------------------------------------------------------------

def test_finding_nothing_exits_zero(stub_search: StubSearch) -> None:
    """No hits → exit 0 with a plain statement. "New kind of problem" is a correct answer for a
    large part of this corpus, so it must not look like a failed run."""
    result = runner.invoke(cli, ["rag", "search", "Coś zupełnie nowego"])

    assert result.exit_code == 0
    assert "Brak trafień" in result.stdout


def test_an_empty_result_says_how_many_the_threshold_cut(stub_search: StubSearch) -> None:
    """Everything cut by the threshold → the count is printed. Without it an empty index and a
    strict threshold look identical on screen, and those call for different fixes."""
    stub_search.result = _result(dropped=4)

    result = runner.invoke(cli, ["rag", "search", "Coś nowego"])

    assert "4" in result.stdout
    assert "RAG_SCORE_MIN" in result.stdout


# --- failure paths ----------------------------------------------------------------------------

def test_an_unreachable_dependency_exits_two(stub_search: StubSearch) -> None:
    """Embedder down → exit 2 and the reason on stderr. Distinct from exit 0 with no hits: one
    means "could not answer", the other "the corpus has nothing"."""
    stub_search.error = EmbeddingError("Embedder timed out")

    result = runner.invoke(cli, ["rag", "search", "Błąd wysyłki"])

    assert result.exit_code == 2
    assert "Embedder timed out" in result.stderr


def test_an_unparseable_query_exits_two(stub_search: StubSearch) -> None:
    """The model's answer did not validate → exit 2, because this run could not answer either."""
    stub_search.error = SearchParseError("nie udało się sparsować zgłoszenia cli")

    result = runner.invoke(cli, ["rag", "search", "Błąd wysyłki"])

    assert result.exit_code == 2
    assert "sparsować" in result.stderr
