from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.db_postgres.table.tickets.table import TICKETS_TABLE

# Fabryka indeksera zgłoszeń: z czego indekser powstaje. Bez usług — budowa klientów z nikim się
# nie łączy.


async def test_the_indexer_writes_to_the_configured_collection_and_table() -> None:
    """Sprawdza, czy indekser zgłoszeń pisze karty do kolekcji, a wątki do tabeli o nazwach
    z konfiguracji: przy `QDRANT_COLLECTION` = `zgloszenia` i `POSTGRES_TICKETS_TABLE` =
    `watki` jego kolekcja nazywa się `zgloszenia`, a tabela `watki`.

    Wyłapuje nazwę zaszytą w kodzie albo wziętą z innego pola: przebudowa golden setu, której
    polecenie podaje własną kolekcję i tabelę, skasowałaby wtedy indeks instancji."""
    settings = Settings(
        _env_file              = None,
        qdrant_collection      = "zgloszenia",
        postgres_tickets_table = "watki",
        postgres_password      = "x",
    )
    indexer = build_tickets_indexer(settings)

    try:
        assert indexer._tickets.name == "zgloszenia"
        assert indexer._threads.name == "watki"
    finally:
        await indexer.aclose()


async def test_by_default_the_indexer_writes_to_the_table_the_tools_read() -> None:
    """Sprawdza, czy bez `POSTGRES_TICKETS_TABLE` indekser pisze wątki do tabeli
    `tickets_text`, tej, którą tabela zgłoszeń ma jako nazwę domyślną.

    Wyłapuje wartość domyślną w konfiguracji, która rozjechała się z nazwą domyślną tabeli:
    stack bez tej zmiennej w `.env` pisałby i czytał wątki z tabeli, której nie zna żadne inne
    miejsce."""
    indexer = build_tickets_indexer(Settings(_env_file=None, postgres_password="x"))

    try:
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
