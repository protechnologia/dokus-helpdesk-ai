from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer

# Fabryka indeksera zgłoszeń: z czego indekser powstaje. Bez usług — budowa klientów z nikim się
# nie łączy.


async def test_the_indexer_writes_to_the_configured_collection() -> None:
    """Sprawdza, czy indekser zgłoszeń pisze do kolekcji o nazwie z konfiguracji: przy
    `QDRANT_COLLECTION` ustawionym na `zgloszenia` jego kolekcja nazywa się `zgloszenia`.

    Wyłapuje nazwę kolekcji zaszytą w kodzie albo wziętą z innego pola: indeksacja pisałaby wtedy do
    innej kolekcji, niż wskazuje konfiguracja."""
    indexer = build_tickets_indexer(Settings(_env_file=None, qdrant_collection="zgloszenia"))

    try:
        assert indexer._tickets.name == "zgloszenia"
    finally:
        await indexer.aclose()


async def test_the_built_indexer_closes_its_clients() -> None:
    """Sprawdza, czy zamknięcie indeksera zbudowanego przez fabrykę zamyka oba połączenia, na
    których on stoi: klienta embeddera i klienta Qdranta.

    Wyłapuje połączenie zostawione otwarte: komenda dostaje z fabryki sam indekser, więc klientów,
    których sama nie zbudowała, nie ma jak zamknąć inaczej."""
    indexer = build_tickets_indexer(Settings(_env_file=None))

    await indexer.aclose()

    assert indexer._embedder._client.is_closed
    assert indexer._tickets._client._client.is_closed
