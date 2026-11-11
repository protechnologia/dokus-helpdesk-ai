"""
Description:
Buduje z konfiguracji serwis, który dokłada zamknięte zgłoszenie do korpusu (p. 30): katalog
korpusu z `TICKETS_CORPUS_DIR`, indekser kart z `factory_tickets_indexer.py` i tabelę wątków
w Postgresie.

Do czego:
Trasa zamknięcia zgłoszenia bierze stąd gotowy serwis, tak jak komendy `helpdesk tickets` biorą
indekser z fabryki obok — sama nie składa klientów.

O czym pamiętać przy zmianach:

- Kto zbudował serwis, ten go zamyka (`ClosedTicketIndexer.aclose()`).
"""

from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.core_service.indexer_closed_ticket import ClosedTicketIndexer
from app.db_postgres import PostgresClient, TicketsTable


def build_closed_ticket_indexer(
    settings: Settings,  # np. Settings()
) -> ClosedTicketIndexer:
    """
    Description:
    Buduje serwis zamkniętego zgłoszenia na klientach z konfiguracji. Nie łączy się z niczym —
    połączenia powstają przy pierwszym użyciu.

    Example args:
        settings=Settings()

    Example result:
        ClosedTicketIndexer piszący do `/code/data/unsafe/corpus`, kolekcji `tickets` i tabeli
        `tickets_text`

    Raises:
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
    """
    postgres = PostgresClient(
        host     = settings.postgres_host,
        port     = settings.postgres_port,
        database = settings.postgres_db,
        user     = settings.postgres_user,
        password = settings.postgres_password,
        timeout  = settings.postgres_timeout_seconds,
    )

    indexer = ClosedTicketIndexer(
        corpus  = settings.tickets_corpus(),
        cards   = build_tickets_indexer(settings),
        threads = TicketsTable(postgres),
    )

    return indexer
