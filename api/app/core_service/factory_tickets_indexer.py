"""
Description:
Buduje indekser zgłoszeń z konfiguracji: klient embeddera, klient Qdranta z kolekcją zgłoszeń
o nazwie z `QDRANT_COLLECTION` i klient Postgresa z tabelą wątków.

Do czego:
Komendy `helpdesk tickets index` i `helpdesk tickets reindex` biorą stąd gotowy indekser, a serwis
zamkniętego zgłoszenia (`factory_closed_ticket_indexer.py`) stawia na nim swój — tak jak trasy
biorą graf z `agent_graphs/factory.py`, same nie składają klientów.

O czym pamiętać przy zmianach:

- Kto zbudował indekser, ten go zamyka (`TicketsIndexer.aclose()`).
"""

from app.config import Settings
from app.core_service.indexer_tickets import TicketsIndexer
from app.db_postgres import PostgresClient, TicketsTable
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
        TicketsIndexer piszący do kolekcji `tickets` i tabeli `tickets_text`

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
    postgres = PostgresClient(
        host     = settings.postgres_host,
        port     = settings.postgres_port,
        database = settings.postgres_db,
        user     = settings.postgres_user,
        password = settings.postgres_password,
        timeout  = settings.postgres_timeout_seconds,
    )

    indexer = TicketsIndexer(
        embedder = embedder,
        tickets  = tickets,
        threads  = TicketsTable(postgres),
    )

    return indexer
