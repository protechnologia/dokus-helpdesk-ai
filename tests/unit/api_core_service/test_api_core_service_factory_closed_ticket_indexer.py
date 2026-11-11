from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import Settings
from app.core_service import factory_closed_ticket_indexer
from app.core_service.factory_closed_ticket_indexer import (
    ClosedTicketConfigError,
    build_closed_ticket_indexer,
    close_process_closed_ticket_indexer,
    get_closed_ticket_indexer,
    process_closed_ticket_indexer,
)
from app.core_service.indexer_closed_ticket import ClosedTicketIndexer
from app.db_postgres.table.tickets.table import TICKETS_TABLE
from tests._helpers.tickets_index import FakeThreads, FakeTickets, closed_ticket_indexer_on

# Fabryka serwisu zamkniętego zgłoszenia: z czego serwis powstaje, kiedy go nie ma i ile żyje.
# Bez usług — budowa klientów z nikim się nie łączy.


@pytest.fixture(autouse=True)
def no_service_left_between_tests() -> Iterator[None]:
    """
    Description:
    Czyści serwis zapamiętany przez fabrykę przed testem i po nim: jest zapamiętywany na cały
    proces, więc bez tego jeden test dostawałby serwis zbudowany w innym.

    Example args:
        (brak)

    Example result:
        None — `process_closed_ticket_indexer()` w teście buduje od nowa
    """
    process_closed_ticket_indexer.cache_clear()

    yield

    process_closed_ticket_indexer.cache_clear()


async def test_the_service_writes_where_the_configuration_points() -> None:
    """Sprawdza, czy serwis pisze pliki do korpusu z `TICKETS_CORPUS_DIR`, karty do kolekcji
    z `QDRANT_COLLECTION`, a wątki do tabeli wątków zgłoszeń, z której czytają narzędzia agenta.

    Wyłapuje ścieżkę albo nazwę zaszytą w kodzie lub wziętą z innego pola: zamknięte zgłoszenie
    trafiałoby wtedy gdzie indziej, niż szukają go komendy `helpdesk tickets` i agent."""
    settings = Settings(
        _env_file               = None,
        llm_generation_provider = "openai",
        tickets_corpus_dir      = Path("/dane/korpus"),
        qdrant_collection       = "zgloszenia",
        postgres_password       = "haslo",
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
    settings = Settings(_env_file=None, llm_generation_provider="openai", postgres_password="x")
    service  = build_closed_ticket_indexer(settings)

    await service.aclose()

    assert service._cards._embedder._client.is_closed
    assert service._cards._tickets._client._client.is_closed


@pytest.mark.parametrize("provider", ["fake", " Fake "])
def test_the_fake_model_gets_no_service(provider: str) -> None:
    """Sprawdza, czy przy atrapie modelu generującego fabryka odmawia błędem
    `ClosedTicketConfigError`, także gdy w konfiguracji stoi „ Fake ” z wielką literą i spacjami.

    Wyłapuje serwis zbudowany przy atrapie modelu: atrapa grafu karty oddaje zawsze tę samą
    zmyśloną kartę, a anonimizator przyjmuje wtedy tekst bez zmian, więc do korpusu trafiłaby
    fałszywa karta, a do `anonymized/` i tabeli wątków dane osobowe."""
    settings = Settings(_env_file=None, llm_generation_provider=provider, postgres_password="x")

    with pytest.raises(ClosedTicketConfigError):
        build_closed_ticket_indexer(settings)


def test_the_service_is_built_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path:    Path,
) -> None:
    """Sprawdza, czy dwa kolejne żądania dostają z zależności trasy ten sam serwis, a budowa
    jest wołana jeden raz.

    Wyłapuje serwis budowany na każde zamknięcie: każde zakładałoby nową pulę połączeń
    z Postgresem, który ładuje słownik w każdej sesji (około 0,6 s), a pule zostawałyby otwarte."""
    built: list[Settings] = []

    def build(settings: Settings) -> ClosedTicketIndexer:
        built.append(settings)

        return closed_ticket_indexer_on(tmp_path, FakeTickets(), FakeThreads())

    monkeypatch.setattr(factory_closed_ticket_indexer, "build_closed_ticket_indexer", build)

    first  = get_closed_ticket_indexer()
    second = get_closed_ticket_indexer()

    assert len(built) == 1
    assert first is second


async def test_closing_closes_the_service_and_forgets_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path:    Path,
) -> None:
    """Sprawdza, czy zamknięcie przy wyłączaniu aplikacji zamyka zbudowany serwis (kolekcję
    zgłoszeń i tabelę wątków) i zapomina go, więc następne użycie zbudowałoby nowy.

    Wyłapuje serwis pominięty przy zamykaniu (jego połączenia zostałyby otwarte) i serwis
    z zamkniętymi połączeniami, który dostałoby następne zamknięcie zgłoszenia."""
    tickets, threads = FakeTickets(), FakeThreads()
    service          = closed_ticket_indexer_on(tmp_path, tickets, threads)

    monkeypatch.setattr(
        factory_closed_ticket_indexer, "build_closed_ticket_indexer", lambda settings: service
    )

    process_closed_ticket_indexer()
    await close_process_closed_ticket_indexer()

    assert (tickets.calls[-1], threads.calls) == ("aclose", ["aclose"])
    assert process_closed_ticket_indexer.cache_info().currsize == 0


async def test_closing_without_a_built_service_builds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sprawdza, czy zamknięcie aplikacji, w której nikt nie zamknął zgłoszenia, niczego nie
    buduje.

    Wyłapuje zamykanie, które najpierw buduje serwis, żeby go zamknąć: przy atrapie modelu
    wyłączenie aplikacji kończyłoby się wtedy błędem konfiguracji, choć nikt korpusu nie
    używał."""
    def build(settings: Settings) -> ClosedTicketIndexer:
        raise AssertionError("serwis nie powinien powstać przy zamykaniu")

    monkeypatch.setattr(factory_closed_ticket_indexer, "build_closed_ticket_indexer", build)

    await close_process_closed_ticket_indexer()

    assert process_closed_ticket_indexer.cache_info().currsize == 0
