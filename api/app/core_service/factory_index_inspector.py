"""
Description:
Buduje z konfiguracji serwis, który liczy indeksy narzędzi agenta (`IndexInspector`), trzyma
jeden taki serwis na proces i podaje go trasie `GET /instance` jako zależność
(`get_index_inspector()`).

Do czego:
Trasa bierze serwis stąd, tak jak trasy grafów biorą graf z `agent_graphs/factory.py` — sama nie
składa klientów. Kolekcje, tabele i katalog paczki mają te same nazwy z konfiguracji, co
w `agent_tools/factory.py`, więc serwis liczy dokładnie to, co czytają narzędzia.

O czym pamiętać przy zmianach:

- Serwis powstaje raz na proces (`process_index_inspector()`), bo nowa sesja Postgresa ładuje
  słownik około 0,6 s; z osobną pulą połączeń, bo narzędzia przy atrapie modelu nie powstają
  wcale. Zamyka go `close_process_index_inspector()` przy wyłączaniu aplikacji.
- Budowa nie łączy się z niczym i nie dotyka dysku — połączenia powstają przy pierwszym
  `inspect()`.
- Nazwa nowej kolekcji albo tabeli narzędzi musi trafić też tutaj, inaczej trasa policzy inny
  indeks niż ten, który czyta narzędzie.
"""

import functools

from app.config import Settings
from app.core_service.inspector_indexes import IndexInspector
from app.core_service.loader_code_description import CodeDescription
from app.db_postgres import DocsTable, PostgresClient, TicketsTable
from app.db_qdrant import DocsCollection, QdrantClient, TicketsCollection


def build_index_inspector(
    settings: Settings,  # np. Settings()
) -> IndexInspector:
    """
    Description:
    Buduje serwis liczący indeksy na klientach Qdranta i Postgresa oraz na katalogu paczki kodu
    z konfiguracji. Nie łączy się z niczym — połączenia powstają przy pierwszym użyciu.

    Example args:
        settings=Settings()

    Example result:
        IndexInspector liczący kolekcje `tickets` i `docs`, tabele `tickets_text` i `docs_text`
        oraz paczkę kodu z /code/data/unsafe/code

    Raises:
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
        DbPostgresConfigError: brak hasła albo pusta nazwa bazy
    """
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    postgres = PostgresClient(
        host     = settings.postgres_host,
        port     = settings.postgres_port,
        database = settings.postgres_db,
        user     = settings.postgres_user,
        password = settings.postgres_password,
        timeout  = settings.postgres_timeout_seconds,
    )

    inspector = IndexInspector(
        tickets_cards   = TicketsCollection(
            client      = qdrant,
            name        = settings.qdrant_collection,
            vector_size = settings.embedding_vector_size,
        ),
        tickets_threads = TicketsTable(postgres),
        docs_sections   = DocsTable(postgres),
        docs_fragments  = DocsCollection(
            client      = qdrant,
            name        = settings.qdrant_docs_collection,
            vector_size = settings.embedding_vector_size,
        ),
        code            = CodeDescription(settings.code_package_dir),
    )

    return inspector


@functools.cache
def process_index_inspector() -> IndexInspector:
    """
    Description:
    Serwis liczący indeksy, zbudowany raz na proces: kolejne żądania dzielą pulę połączeń
    Postgresa i połączenia HTTP do Qdranta.

    Example args:
        (brak)

    Example result:
        IndexInspector na klientach z konfiguracji

    Raises:
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
        DbPostgresConfigError: brak hasła albo pusta nazwa bazy
    """
    return build_index_inspector(Settings())


def get_index_inspector() -> IndexInspector:
    """
    Description:
    Zależność FastAPI: skąd trasa `GET /instance` bierze serwis liczący indeksy. Osobna od
    `process_index_inspector()`, żeby test mógł ją podmienić (`app.dependency_overrides`), tak
    jak `get_graph_builder()` przy trasach grafów.

    Example args:
        (brak)

    Example result:
        IndexInspector zbudowany raz na proces
    """
    return process_index_inspector()


async def close_process_index_inspector() -> None:
    """
    Description:
    Zamyka serwis zbudowany przez `process_index_inspector()` i zapomina go. Gdy żadnego nie
    zbudowano — nikt nie zapytał o `GET /instance` — nie robi nic. Woła to aplikacja przy
    wyłączaniu.

    Example args:
        (brak)

    Example result:
        None
    """
    # --- nic nie powstało: nie ma czego zamykać ---
    if not process_index_inspector.cache_info().currsize:
        return

    await process_index_inspector().aclose()

    process_index_inspector.cache_clear()
