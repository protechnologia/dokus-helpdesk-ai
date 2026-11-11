from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.db_postgres.table.tickets.table import TICKETS_TABLE

# Fabryka indeksera zgłoszeń: z czego indekser powstaje. Bez usług — budowa klientów z nikim się
# nie łączy.


async def test_the_indexer_writes_to_the_configured_collection_and_the_threads_table() -> None:
    """Sprawdza, czy indekser zgłoszeń pisze karty do kolekcji o nazwie z konfiguracji (przy
    `QDRANT_COLLECTION` ustawionym na `zgloszenia` jego kolekcja nazywa się `zgloszenia`),
    a wątki do tabeli wątków zgłoszeń, z której czytają narzędzia agenta.

    Wyłapuje nazwę kolekcji zaszytą w kodzie albo wziętą z innego pola oraz tabelę inną niż ta,
    w której szukają narzędzia: indeksacja pisałaby wtedy gdzie indziej, niż szuka agent."""
    settings = Settings(_env_file=None, qdrant_collection="zgloszenia", postgres_password="x")
    indexer  = build_tickets_indexer(settings)

    try:
        assert indexer._tickets.name == "zgloszenia"
        assert indexer._threads.name == TICKETS_TABLE
    finally:
        await indexer.aclose()


async def test_the_built_indexer_closes_its_clients() -> None:
    """Sprawdza, czy zamknięcie indeksera zbudowanego przez fabrykę zamyka połączenia, na których
    on stoi: klienta embeddera i klienta Qdranta.

    Wyłapuje połączenie zostawione otwarte: komenda dostaje z fabryki sam indekser, więc klientów,
    których sama nie zbudowała, nie ma jak zamknąć inaczej."""
    indexer = build_tickets_indexer(Settings(_env_file=None, postgres_password="x"))

    await indexer.aclose()

    assert indexer._embedder._client.is_closed
    assert indexer._tickets._client._client.is_closed
