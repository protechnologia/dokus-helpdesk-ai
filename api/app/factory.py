import logging
from functools import lru_cache

from app.config import Settings
from app.embedding import EmbeddingClient
from app.llm import get_llm_client
from app.retrieval import QdrantClient
from app.service.parser_ticket_parsed import TicketParser
from app.service.rag_searcher import RagSearcher

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Description:
    The application's configuration, read once. Cached because `Settings()` re-reads the
    environment and `.env` on every construction, and a handler doing that per request would pay
    for disk I/O to learn what cannot change while the process runs.

    Example args:
        (none)

    Example result:
        Settings(qdrant_url="http://qdrant:6333", rag_top_k=5, …)
    """
    return Settings()


def build_searcher(
    settings: Settings,  # e.g. Settings(qdrant_collection="tickets", rag_top_k=5)
) -> RagSearcher:
    """
    Description:
    Builds the search service from configuration. The single construction path, shared by the HTTP
    handler and the CLI: two places assembling this would drift apart the moment a setting is
    added, and a CLI quietly searching with different parameters than the API is exactly the kind
    of divergence nothing would report.

    The transport clients stay inside the service. A caller that must clean up calls
    `searcher.aclose()`, so nobody outside this file needs to know what the service is built
    from — adding a dependency stays a change here.

    Example args:
        settings=Settings(qdrant_url="http://qdrant:6333", rag_top_k=5)

    Example result:
        RagSearcher querying the `tickets` collection with top_k=5

    Raises:
        LLMConfigError: the LLM provider is misconfigured
        RetrievalConfigError: `QDRANT_URL` or `QDRANT_COLLECTION` is empty
    """
    searcher = RagSearcher(
        parser   = TicketParser(llm=get_llm_client(settings)),
        embedder = EmbeddingClient(
            base_url = settings.embedding_base_url,
            timeout  = settings.embedding_timeout_seconds,
        ),
        qdrant = QdrantClient(
            base_url   = settings.qdrant_url,
            collection = settings.qdrant_collection,
            timeout    = settings.qdrant_timeout_seconds,
        ),
        top_k     = settings.rag_top_k,
        score_min = settings.rag_score_min,
    )

    # Configuration only — no secrets, no endpoints beyond the collection being served.
    logger.info(
        "searcher ready collection=%s top_k=%d score_min=%.3f",
        settings.qdrant_collection,
        settings.rag_top_k,
        settings.rag_score_min,
    )

    return searcher


@lru_cache(maxsize=1)
def get_searcher() -> RagSearcher:
    """
    Description:
    The search service as HTTP handlers get it: built once, reused for every request. This module
    is where handlers obtain their domain services — the same role `llm/factory.py` plays for one
    transport client, at the level of the whole application.

    Cached deliberately, and this is the important part: both transport clients hold an HTTP
    connection pool, and building them per request would open a fresh pool per call — losing
    connection reuse and eventually exhausting sockets under load. The LLM client is built here
    for the same reason, and additionally because `get_llm_client()` fails fast on bad
    configuration: with the cache that failure happens on the first request rather than on every
    one, and it surfaces as a 500 with a stack rather than as a green container quietly answering
    503 forever (CLAUDE.md -> "Logi i obserwowalność").

    `aclose()` is never called on the result: a server keeps its pools for the life of the
    process, which is what a pool is for.

    Example args:
        (none)

    Example result:
        RagSearcher querying the `tickets` collection with top_k=5

    Raises:
        LLMConfigError: the LLM provider is misconfigured — a startup-class failure that must not
            be dressed up as a transient one
    """
    return build_searcher(get_settings())
