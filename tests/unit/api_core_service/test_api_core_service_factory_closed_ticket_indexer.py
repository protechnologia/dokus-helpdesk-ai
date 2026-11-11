from pathlib import Path

from app.config import Settings
from app.core_service.factory_closed_ticket_indexer import build_closed_ticket_indexer
from app.db_postgres.table.tickets.table import TICKETS_TABLE

# Fabryka serwisu zamkniętego zgłoszenia: z czego serwis powstaje. Bez usług — budowa klientów
# z nikim się nie łączy.


async def test_the_service_writes_where_the_configuration_points() -> None:
    """Sprawdza, czy serwis pisze pliki do korpusu z `TICKETS_CORPUS_DIR`, karty do kolekcji
    z `QDRANT_COLLECTION`, a wątki do tabeli wątków zgłoszeń, z której czytają narzędzia agenta.

    Wyłapuje ścieżkę albo nazwę zaszytą w kodzie lub wziętą z innego pola: zamknięte zgłoszenie
    trafiałoby wtedy gdzie indziej, niż szukają go komendy `helpdesk tickets` i agent."""
    settings = Settings(
        _env_file          = None,
        tickets_corpus_dir = Path("/dane/korpus"),
        qdrant_collection  = "zgloszenia",
        postgres_password  = "haslo",
    )
    service = build_closed_ticket_indexer(settings)

    try:
        assert service._corpus.root         == Path("/dane/korpus")
        assert service._cards._tickets.name == "zgloszenia"
        assert service._threads.name        == TICKETS_TABLE
    finally:
        await service.aclose()


async def test_the_built_service_closes_its_clients() -> None:
    """Sprawdza, czy zamknięcie serwisu zbudowanego przez fabrykę zamyka połączenia embeddera
    i Qdranta, na których stoi indekser kart.

    Wyłapuje połączenie zostawione otwarte: trasa dostaje z fabryki sam serwis, więc klientów,
    których sama nie zbudowała, nie ma jak zamknąć inaczej."""
    service = build_closed_ticket_indexer(Settings(_env_file=None, postgres_password="haslo"))

    await service.aclose()

    assert service._cards._embedder._client.is_closed
    assert service._cards._tickets._client._client.is_closed
