import logging

from app.embedding import EmbeddingClient
from app.model.rag_search_result import SearchResult
from app.model.ticket_raw import RawTicket
from app.retrieval import VECTOR_PROBLEM, QdrantClient
from app.service.parser_ticket_parsed import TicketParser

logger = logging.getLogger(__name__)


class SearchParseError(Exception):
    """
    Description:
    The incoming ticket could not be parsed into the shape a search needs. Its own type because the
    caller has to tell it apart from a transport failure: an unparseable ticket is about the INPUT
    (the handler answers 422), while an unreachable embedder is about the stack (503).
    """


class RagSearcher:
    """
    Description:
    Finds historical tickets resembling a new one: parse, embed, query, threshold.

    Do czego:
    The runtime half of retrieval, mirroring `TicketIndexer` on the offline side. Both exist so
    that no handler ever holds this sequence itself — the CLI and `POST /search` are thin adapters
    over this one method.

    Flow:
        1. `search()` parses the incoming thread with the SAME prompt and model that built the
           corpus, so both sides of the comparison are the same kind of text.
        2. `embedding_text()` on the parsed ticket builds the text to embed — never assembled
           here, see the note in `_vector_for`.
        3. The text is embedded in QUERY mode and matched against the `problem` (passage) vectors.
        4. Hits below `score_min` are dropped, counted and reported rather than silently lost.

    Why the incoming ticket is parsed at all, rather than embedded raw: a raw mail carries a
    greeting, a signature and quoted history, all of which pollute the query vector. Parsing costs
    one extra LLM call in a flow that already calls an LLM to generate the answer (CLAUDE.md ->
    "RAG — architektura").
    """

    def __init__(
        self,
        parser:    TicketParser,     # e.g. TicketParser(llm=FakeLLMClient())
        embedder:  EmbeddingClient,  # e.g. EmbeddingClient(base_url="http://embedder:8000")
        qdrant:    QdrantClient,     # e.g. QdrantClient(base_url="http://qdrant:6333", …)
        top_k:     int,              # e.g. 5 — RAG_TOP_K
        score_min: float,            # e.g. 0.0 — RAG_SCORE_MIN, cosine similarity
    ):
        """
        Description:
        Wires the searcher to the three services it needs and to the two tuning knobs. Everything
        is injected: the domain never builds a client or reads configuration of its own (rule 4).

        Example args:
            parser=TicketParser(llm=FakeLLMClient())
            embedder=EmbeddingClient(base_url="http://embedder:8000")
            qdrant=QdrantClient(base_url="http://qdrant:6333", collection="tickets")
            top_k=5
            score_min=0.0

        Example result:
            RagSearcher ready to answer `search()`
        """
        self._parser    = parser
        self._embedder  = embedder
        self._qdrant    = qdrant
        self._top_k     = top_k
        self._score_min = score_min

    async def search(
        self,
        raw: RawTicket,  # e.g. RawTicket(ticket_id="41002", subject="Błąd wysyłki", …)
    ) -> SearchResult:
        """
        Description:
        Finds the records most similar to one incoming ticket.

        Example args:
            raw=RawTicket(ticket_id="41002", date=date(2026, 8, 19), subject="Błąd wysyłki", …)

        Example result:
            SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

        Raises:
            SearchParseError: the model's answer did not validate as a ticket
            LLMError: the provider itself failed
            EmbeddingError: the embedder is unreachable or answered with an error
            RetrievalError: Qdrant is unreachable or answered with an error
        """
        # --- parse: the same prompt and model that produced the corpus ---
        parsed = await self._parser.parse(raw)

        # A parse that failed is about the INPUT, so it must not surface as a transport error. The
        # reasons come from the validator and name the offending fields.
        if parsed.ticket is None:
            raise SearchParseError(
                f"nie udało się sparsować zgłoszenia {raw.ticket_id}: {'; '.join(parsed.errors)}"
            )

        # --- embed and query ---
        vector = await self._vector_for(parsed.ticket.embedding_text())
        hits   = await self._qdrant.search(
            vector      = vector,
            # Always the passage side: a query vector may only be matched against `problem`
            # vectors, never against `sts` ones (CLAUDE.md -> "Embeddingi"). Searching the wrong
            # space is not an error — it returns plausible-looking nonsense.
            vector_name = VECTOR_PROBLEM,
            limit       = self._top_k,
        )

        # --- threshold ---
        kept    = [hit for hit in hits if hit.score >= self._score_min]
        dropped = len(hits) - len(kept)

        # Ids and counts only: payloads carry ticket content, i.e. customer data, which belongs to
        # DEBUG at most (CLAUDE.md -> "Logi i obserwowalność").
        logger.info(
            "search ticket_id=%s hits=%d dropped=%d score_min=%.3f",
            raw.ticket_id,
            len(kept),
            dropped,
            self._score_min,
        )

        return SearchResult(
            query                   = parsed.ticket,
            hits                    = kept,
            dropped_below_threshold = dropped,
        )

    async def _vector_for(
        self,
        text: str,  # e.g. "Wysyłka przez ePUAP kończy się błędem\nPo kliknięciu Wyślij…"
    ) -> list[float]:
        """
        Description:
        Embeds the query text in QUERY mode and returns the single vector.

        The text arrives ready-made from `embedding_text()` and is NEVER assembled here. Indexing
        builds it the same way; two call sites doing it by hand would drift apart and produce
        vectors nobody can compare — and nothing would fail loudly, because both sides would still
        return well-formed vectors and Qdrant would still return scored hits.

        Example args:
            text="Wysyłka przez ePUAP kończy się błędem komunikacji"

        Example result:
            [0.0123, -0.0456, …]

        Raises:
            EmbeddingError: the embedder is unreachable or answered with an error
        """
        vectors = await self._embedder.embed_query([text])

        return vectors[0]
