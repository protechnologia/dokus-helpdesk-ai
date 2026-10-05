from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer

# Fabryka indeksera zgłoszeń: z czego indekser powstaje. Bez usług — budowa klientów z nikim się
# nie łączy.


async def test_the_indexer_writes_to_the_configured_collection() -> None:
    """`QDRANT_COLLECTION` w konfiguracji → indekser z kolekcją o tej nazwie."""
    indexer = build_tickets_indexer(Settings(_env_file=None, qdrant_collection="zgloszenia"))

    try:
        assert indexer._tickets.name == "zgloszenia"
    finally:
        await indexer.aclose()


async def test_the_built_indexer_closes_its_clients() -> None:
    """`aclose()` zbudowanego indeksera → zamknięty klient embeddera i klient Qdranta."""
    indexer = build_tickets_indexer(Settings(_env_file=None))

    await indexer.aclose()

    assert indexer._embedder._client.is_closed
    assert indexer._tickets._client._client.is_closed
