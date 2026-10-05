"""
Description:
Buduje indekser zgłoszeń z konfiguracji: klient embeddera, klient Qdranta i kolekcja zgłoszeń
o nazwie z `QDRANT_COLLECTION`.

Do czego:
Komendy `helpdesk rag index` i `helpdesk rag reindex` biorą stąd gotowy indekser, tak jak trasy
biorą graf z `agent_graphs/factory.py` — same nie składają klientów.

O czym pamiętać przy zmianach:

- Kto zbudował indekser, ten go zamyka (`TicketsIndexer.aclose()`).
"""

from app.config import Settings
from app.core_service.indexer_tickets import TicketsIndexer
from app.db_qdrant import QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient


def build_tickets_indexer(
    settings: Settings,  # np. Settings()
) -> TicketsIndexer:
    """
    Description:
    Buduje indekser zgłoszeń na klientach z konfiguracji. Nie łączy się z niczym — połączenia
    powstają przy pierwszym użyciu.

    Example args:
        settings=Settings()

    Example result:
        TicketsIndexer piszący do kolekcji `tickets`

    Raises:
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
    """
    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    tickets = TicketsCollection(
        client      = qdrant,
        name        = settings.qdrant_collection,
        vector_size = settings.embedding_vector_size,
    )

    return TicketsIndexer(embedder=embedder, tickets=tickets)
