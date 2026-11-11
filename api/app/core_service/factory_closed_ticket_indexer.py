"""
Description:
Buduje z konfiguracji serwis, który dokłada zamknięte zgłoszenie do korpusu (p. 30): katalog
korpusu z `TICKETS_CORPUS_DIR`, indekser kart z `factory_tickets_indexer.py` i tabelę wątków
w Postgresie. Trzyma jeden taki serwis na proces i podaje go trasie `POST /tickets/closed` jako
zależność (`get_closed_ticket_indexer()`).

Do czego:
Trasa zamknięcia zgłoszenia bierze stąd gotowy serwis, tak jak komendy `helpdesk tickets` biorą
indekser z fabryki obok — sama nie składa klientów.

O czym pamiętać przy zmianach:

- Przy atrapie modelu generującego (`LLM_GENERATION_PROVIDER=fake`) serwisu nie ma:
  `build_closed_ticket_indexer()` odmawia błędem konfiguracji. Atrapa grafu karty oddaje zawsze
  tę samą zmyśloną kartę, a anonimizator przyjmuje wtedy wynik atrapy silnika, który oddaje
  tekst bez zmian — do korpusu trafiłaby fałszywa karta, a do `anonymized/` i tabeli wątków
  tekst z danymi osobowymi.
- Serwis powstaje raz na proces (`process_closed_ticket_indexer()`), bo nowa sesja Postgresa
  ładuje słownik około 0,6 s. Zamyka go `close_process_closed_ticket_indexer()` przy wyłączaniu
  aplikacji.
- Budowa nie łączy się z niczym i nie dotyka dysku — połączenia powstają przy pierwszym `add()`.
"""

import functools

from app.config import Settings
from app.core_service.factory_tickets_indexer import build_tickets_indexer
from app.core_service.indexer_closed_ticket import ClosedTicketIndexer
from app.db_postgres import PostgresClient, TicketsTable
from app.engine_llm.factory import PROVIDER_FAKE


class ClosedTicketConfigError(Exception):
    """
    Description:
    Konfiguracja nie pozwala dokładać zamkniętych zgłoszeń do korpusu: model generujący jest
    atrapą. Błąd konfiguracji, więc trasa kończy się 500, a nie 503 — czekanie go nie naprawi.
    """


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
        ClosedTicketConfigError: model generujący jest atrapą
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
    """
    # Wartość z ENV wpisuje człowiek: wielkość liter i spacje czyta się tak jak w fabryce grafów.
    if settings.llm_generation_provider.strip().lower() == PROVIDER_FAKE:
        raise ClosedTicketConfigError(
            "korpus przyjmuje tylko karty prawdziwego modelu, a LLM_GENERATION_PROVIDER=fake"
        )

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


@functools.cache
def process_closed_ticket_indexer() -> ClosedTicketIndexer:
    """
    Description:
    Serwis zamkniętego zgłoszenia zbudowany raz na proces: kolejne zamknięcia dzielą pulę
    połączeń Postgresa i połączenia HTTP do embeddera i Qdranta. Odmowa przy atrapie modelu nie
    jest zapamiętywana, więc pada przy każdym żądaniu.

    Example args:
        (brak)

    Example result:
        ClosedTicketIndexer na klientach z konfiguracji

    Raises:
        ClosedTicketConfigError: model generujący jest atrapą
        EmbeddingConfigError: pusty adres embeddera
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
    """
    return build_closed_ticket_indexer(Settings())


def get_closed_ticket_indexer() -> ClosedTicketIndexer:
    """
    Description:
    Zależność FastAPI: skąd trasa `POST /tickets/closed` bierze serwis. Osobna od
    `process_closed_ticket_indexer()`, żeby test mógł ją podmienić (`app.dependency_overrides`),
    tak jak `get_graph_builder()` przy trasach grafów.

    Example args:
        (brak)

    Example result:
        ClosedTicketIndexer zbudowany raz na proces
    """
    return process_closed_ticket_indexer()


async def close_process_closed_ticket_indexer() -> None:
    """
    Description:
    Zamyka serwis zbudowany przez `process_closed_ticket_indexer()` i zapomina go. Gdy żadnego
    nie zbudowano — nikt nie zamknął zgłoszenia albo model jest atrapą — nie robi nic. Woła to
    aplikacja przy wyłączaniu.

    Example args:
        (brak)

    Example result:
        None
    """
    # --- nic nie powstało: nie ma czego zamykać ---
    if not process_closed_ticket_indexer.cache_info().currsize:
        return

    await process_closed_ticket_indexer().aclose()

    process_closed_ticket_indexer.cache_clear()
