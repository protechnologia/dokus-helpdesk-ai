from datetime import date

import pytest

from app.model.ticket_parse_result import ParseResult
from app.model.ticket_parsed import ParsedTicket
from app.model.ticket_raw import RawTicket
from app.retrieval import VECTOR_PROBLEM, TicketHit
from app.service.rag_searcher import RagSearcher, SearchParseError

VECTOR_SIZE = 4

PARSED_FIELDS = {
    "ticket_id":                     "41002",
    "date":                          "2026-08-19",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "brak",
    # A recognisable sentence rather than "brak": this value is asserted to be ABSENT from the
    # embedded text, and a short common word would match by accident inside the symptoms.
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "brak",
}

RAW = RawTicket(
    ticket_id = "41002",
    date      = date(2026, 8, 19),
    category  = "Błąd",
    subject   = "Błąd wysyłki",
    body      = "Nie mogę wysłać pisma przez ePUAP, wyskakuje błąd komunikacji.",
)


class FakeParser:
    """
    Description:
    Stands in for `TicketParser`, returning a prepared `ParseResult` and recording what it was
    asked to parse.

    A stub rather than the production `FakeLLMClient` behind a real parser: this file tests what
    the SEARCHER does with a parse, and driving that through a fake model's canned JSON would make
    every assertion depend on the prompt as well.
    """

    def __init__(self, result: ParseResult) -> None:
        """
        Description:
        Builds the stub with the result it will hand back.

        Example args:
            result=ParseResult(ticket_id="41002", ticket=ParsedTicket(…))

        Example result:
            FakeParser recording into `seen`
        """
        self._result = result
        self.seen: list[RawTicket] = []

    async def parse(self, raw: RawTicket) -> ParseResult:
        """
        Description:
        Records the ticket and returns the prepared result.

        Example args:
            raw=RawTicket(ticket_id="41002", …)

        Example result:
            ParseResult(ticket_id="41002", ticket=ParsedTicket(…))
        """
        self.seen.append(raw)

        return self._result


class FakeEmbedder:
    """
    Description:
    Stands in for `EmbeddingClient`, recording which MODE the query was embedded in.

    The mode is the point: a query vector may only be matched against `passage` vectors, and a
    mix-up is invisible afterwards — the wrong space still answers, just slightly worse. So the
    stub implements all three modes and the tests assert that only `query` was ever used.
    """

    def __init__(self) -> None:
        """
        Description:
        Builds the stub with empty call logs.

        Example args:
            (none)

        Example result:
            FakeEmbedder with `query_batches`, `passage_batches` and `sts_batches` empty
        """
        self.query_batches:   list[list[str]] = []
        self.passage_batches: list[list[str]] = []
        self.sts_batches:     list[list[str]] = []

    async def embed_query(self, texts: list[str]) -> list[list[float]]:
        """
        Description:
        Records the batch and returns one vector per text.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            [[1.0, 1.0, 1.0, 1.0]]
        """
        self.query_batches.append(texts)

        return [[1.0] * VECTOR_SIZE for _ in texts]

    async def embed_passage(self, texts: list[str]) -> list[list[float]]:
        """
        Description:
        Records a call that should never happen during a search.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            [[2.0, 2.0, 2.0, 2.0]]
        """
        self.passage_batches.append(texts)

        return [[2.0] * VECTOR_SIZE for _ in texts]

    async def embed_sts(self, texts: list[str]) -> list[list[float]]:
        """
        Description:
        Records a call that should never happen during a search.

        Example args:
            texts=["Wysyłka przez ePUAP…"]

        Example result:
            [[3.0, 3.0, 3.0, 3.0]]
        """
        self.sts_batches.append(texts)

        return [[3.0] * VECTOR_SIZE for _ in texts]


class FakeQdrant:
    """
    Description:
    Stands in for `QdrantClient`, returning prepared hits and recording how it was queried.

    Records the vector NAME as well as the limit: the collection holds two spaces and querying
    the wrong one returns plausible hits rather than an error, so the name is worth asserting.
    """

    def __init__(self, hits: list[TicketHit]) -> None:
        """
        Description:
        Builds the stub with the hits it will return.

        Example args:
            hits=[TicketHit(point_id="a", score=0.9, payload={"ticket_id": "33644"})]

        Example result:
            FakeQdrant recording into `queries`
        """
        self._hits = hits
        self.queries: list[dict] = []

    async def search(
        self,
        vector:      list[float],
        vector_name: str,
        limit:       int,
    ) -> list[TicketHit]:
        """
        Description:
        Records the query and returns the prepared hits.

        Example args:
            vector=[1.0, 1.0, 1.0, 1.0]
            vector_name="problem"
            limit=5

        Example result:
            [TicketHit(point_id="a", score=0.9, payload={"ticket_id": "33644"})]
        """
        self.queries.append({"vector": vector, "using": vector_name, "limit": limit})

        return self._hits


def _hit(ticket_id: str, score: float) -> TicketHit:
    """
    Description:
    Builds one hit with a recognisable id and score, so threshold assertions read as a list of
    ids rather than as a list of objects.

    Example args:
        ticket_id="33644"
        score=0.9

    Example result:
        TicketHit(point_id="p-33644", score=0.9, payload={"ticket_id": "33644"})
    """
    return TicketHit(
        point_id = f"p-{ticket_id}",
        score    = score,
        payload  = {"ticket_id": ticket_id, "solution": "Wygenerowano certyfikat."},
    )


def _searcher(
    hits:      list[TicketHit],
    score_min: float = 0.0,
    top_k:     int   = 5,
    parsed:    ParsedTicket | None = None,
) -> tuple[RagSearcher, FakeParser, FakeEmbedder, FakeQdrant]:
    """
    Description:
    Builds a searcher over the three stubs and hands them back for assertions. One helper per
    axis this file exercises, so no test assembles the rigging by hand.

    Example args:
        hits=[TicketHit(point_id="a", score=0.9, payload={})]
        score_min=0.5

    Example result:
        (RagSearcher, FakeParser, FakeEmbedder, FakeQdrant)
    """
    ticket = parsed if parsed is not None else ParsedTicket.model_validate(PARSED_FIELDS)
    parser = FakeParser(ParseResult(ticket_id="41002", ticket=ticket))

    embedder = FakeEmbedder()
    qdrant   = FakeQdrant(hits)
    searcher = RagSearcher(
        parser    = parser,
        embedder  = embedder,
        qdrant    = qdrant,
        top_k     = top_k,
        score_min = score_min,
    )

    return searcher, parser, embedder, qdrant


# --- the query side -------------------------------------------------------------------------

async def test_query_is_embedded_in_query_mode_only() -> None:
    """search() → the incoming ticket is embedded as a QUERY, never as passage or sts. A mode
    mix-up costs a few points of recall and never raises, so it has to be asserted."""
    searcher, _, embedder, _ = _searcher([_hit("33644", 0.9)])

    await searcher.search(RAW)

    assert len(embedder.query_batches) == 1
    assert embedder.passage_batches    == []
    assert embedder.sts_batches        == []


async def test_query_text_comes_from_the_model_not_from_the_service() -> None:
    """The embedded text is exactly `embedding_text()` of the parsed ticket. Indexing builds it
    the same way; a service assembling it by hand would drift apart from the index silently."""
    parsed                   = ParsedTicket.model_validate(PARSED_FIELDS)
    searcher, _, embedder, _ = _searcher([_hit("33644", 0.9)], parsed=parsed)

    await searcher.search(RAW)

    assert embedder.query_batches[0] == [parsed.embedding_text()]
    # `solution` must not reach the vector — we search by similarity of the PROBLEM.
    assert parsed.solution not in embedder.query_batches[0][0]


async def test_search_goes_against_the_problem_vectors() -> None:
    """The query is matched against the `problem` (passage) space, never against `sts`: mixing
    the sides is not an error, it just returns worse hits."""
    searcher, _, _, qdrant = _searcher([_hit("33644", 0.9)])

    await searcher.search(RAW)

    assert qdrant.queries[0]["using"] == VECTOR_PROBLEM


async def test_top_k_is_passed_through() -> None:
    """RAG_TOP_K reaches Qdrant as the limit: it is the pool the threshold narrows down."""
    searcher, _, _, qdrant = _searcher([_hit("33644", 0.9)], top_k=10)

    await searcher.search(RAW)

    assert qdrant.queries[0]["limit"] == 10


async def test_the_whole_thread_is_handed_to_the_parser() -> None:
    """The raw ticket travels to the parser untouched — a search parses the same way the corpus
    was parsed, which is what makes both sides of the comparison the same kind of text."""
    searcher, parser, _, _ = _searcher([_hit("33644", 0.9)])

    await searcher.search(RAW)

    assert parser.seen == [RAW]


# --- the threshold --------------------------------------------------------------------------

async def test_hits_below_the_threshold_are_dropped_and_counted() -> None:
    """Hits under RAG_SCORE_MIN are removed but REPORTED: a caller has to tell "nothing found"
    from "the threshold cut it", and the count is the only thing that says which."""
    searcher, _, _, _ = _searcher(
        [_hit("33644", 0.9), _hit("10718", 0.4), _hit("6773", 0.1)],
        score_min = 0.5,
    )

    result = await searcher.search(RAW)

    assert [hit.ticket_id for hit in result.hits] == ["33644"]
    assert result.dropped_below_threshold         == 2


async def test_a_hit_exactly_on_the_threshold_is_kept() -> None:
    """score == RAG_SCORE_MIN passes: the threshold is a minimum, and an off-by-one here would
    quietly drop the marginal hits the tuning is about."""
    searcher, _, _, _ = _searcher([_hit("33644", 0.5)], score_min=0.5)

    result = await searcher.search(RAW)

    assert [hit.ticket_id for hit in result.hits] == ["33644"]
    assert result.dropped_below_threshold         == 0


async def test_the_default_threshold_cuts_nothing() -> None:
    """With RAG_SCORE_MIN at its 0.0 default every hit survives — deliberate until stage 5.7
    measures a value: near-identical problems with disjoint causes must all reach the prompt."""
    searcher, _, _, _ = _searcher([_hit("33644", 0.9), _hit("10718", 0.02)])

    result = await searcher.search(RAW)

    assert len(result.hits)               == 2
    assert result.dropped_below_threshold == 0


async def test_finding_nothing_is_a_result_not_a_failure() -> None:
    """An empty index or no match → an empty result, not an exception. "New kind of problem" is
    the correct answer for 47% of this corpus (singletons), so it is a state, not an error."""
    searcher, _, _, _ = _searcher([])

    result = await searcher.search(RAW)

    assert result.hits    == []
    assert result.is_empty is True


async def test_everything_cut_by_the_threshold_is_still_reported() -> None:
    """All hits below the threshold → empty result carrying the count. Without it a strict
    threshold looks exactly like an empty index."""
    searcher, _, _, _ = _searcher([_hit("33644", 0.2)], score_min=0.9)

    result = await searcher.search(RAW)

    assert result.is_empty                is True
    assert result.dropped_below_threshold == 1


# --- the parsed query -----------------------------------------------------------------------

async def test_the_parsed_query_travels_with_the_result() -> None:
    """The result carries what was actually searched for: the model rewrote a raw thread, and an
    unexpected reading is the first thing that explains a surprising hit list."""
    searcher, _, _, _ = _searcher([_hit("33644", 0.9)])

    result = await searcher.search(RAW)

    assert result.query.problem == PARSED_FIELDS["problem"]


async def test_an_unparseable_ticket_is_its_own_error() -> None:
    """A rejected parse → SearchParseError naming the ticket, not a transport error: this is about
    the INPUT, so the handler answers 422 rather than 503."""
    parser = FakeParser(
        ParseResult(ticket_id="41002", errors=["pole 'problem' jest wymagane"])
    )
    searcher = RagSearcher(
        parser    = parser,
        embedder  = FakeEmbedder(),
        qdrant    = FakeQdrant([]),
        top_k     = 5,
        score_min = 0.0,
    )

    with pytest.raises(SearchParseError, match="41002"):
        await searcher.search(RAW)


async def test_a_failed_parse_never_reaches_the_index() -> None:
    """A rejected parse stops before embedding and before Qdrant — no point paying for a vector
    of a ticket we could not read."""
    parser   = FakeParser(ParseResult(ticket_id="41002", errors=["niepoprawny JSON"]))
    embedder = FakeEmbedder()
    qdrant   = FakeQdrant([])
    searcher = RagSearcher(
        parser    = parser,
        embedder  = embedder,
        qdrant    = qdrant,
        top_k     = 5,
        score_min = 0.0,
    )

    with pytest.raises(SearchParseError):
        await searcher.search(RAW)

    assert embedder.query_batches == []
    assert qdrant.queries         == []
