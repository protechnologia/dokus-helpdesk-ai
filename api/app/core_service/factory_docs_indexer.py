"""
Description:
Buduje indekser dokumentacji z konfiguracji i mówi, do którego indeksu on pisze. Jedyne miejsce,
które zna oba indeksy dokumentacji:

| indeks      | tabela w Postgresie   | kolekcja w Qdrancie         | co trzyma              |
|-------------|-----------------------|-----------------------------|------------------------|
| właściwy    | `docs_text`           | `QDRANT_DOCS_COLLECTION`    | dokumentacja aplikacji |
| syntetyczny | `docs_text_synthetic` | ta sama nazwa `_synthetic`  | paczka zmyślona z repo |

Do czego:
Komenda `helpdesk docs index` bierze stąd gotowy indekser, tak jak trasy biorą graf z
`agent_graphs/factory.py` — sama nie składa klientów. Z `docs_index_names()` korzysta też ten,
kto chce czytać indeks syntetyczny: testy i pomiary narzędzi dokumentacji.

O czym pamiętać przy zmianach:

- Paczka zmyślona ma własny indeks, żeby nie mogła się zmieszać z dokumentacją, z której
  odpowiada agent. Importer dostaje tę samą flagę co nazwy, więc dokumentu z niewłaściwą flagą
  w manifeście nie przyjmie.
- Kto zbudował indekser, ten go zamyka (`DocsIndexer.aclose()`).
"""

from app.config import Settings
from app.core_service.indexer_docs import DocsIndexer
from app.db_postgres import DOCS_TABLE, DocsTable, PostgresClient
from app.db_qdrant import DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient

# Dopisek do nazw tabeli i kolekcji indeksu syntetycznego.
SYNTHETIC_SUFFIX = "_synthetic"


def docs_index_names(
    settings:  Settings,  # np. Settings(qdrant_docs_collection="docs", …)
    synthetic: bool,      # True dla indeksu paczki zmyślonej
) -> tuple[str, str]:
    """
    Description:
    Oddaje nazwę tabeli w Postgresie i kolekcji w Qdrancie jednego indeksu dokumentacji:
    właściwego albo syntetycznego.

    Example args:
        settings=Settings(qdrant_docs_collection="docs")
        synthetic=True

    Example result:
        ("docs_text_synthetic", "docs_synthetic")
    """
    suffix = SYNTHETIC_SUFFIX if synthetic else ""
    names  = (f"{DOCS_TABLE}{suffix}", f"{settings.qdrant_docs_collection}{suffix}")

    return names


def build_docs_indexer(
    settings:  Settings,  # np. Settings()
    synthetic: bool,      # True, gdy indekser ma pisać do indeksu syntetycznego
) -> DocsIndexer:
    """
    Description:
    Buduje indekser dokumentacji na klientach z konfiguracji: embedder, Postgres i Qdrant,
    z tabelą i kolekcją wybranego indeksu. Nie łączy się z niczym — połączenia powstają przy
    pierwszym użyciu.

    Example args:
        settings=Settings()
        synthetic=False

    Example result:
        DocsIndexer piszący do tabeli `docs_text` i kolekcji `docs`

    Raises:
        EmbeddingConfigError: pusty adres embeddera
        DbPostgresConfigError: brak hasła albo pusta nazwa bazy
        DbQdrantConfigError: niedozwolona nazwa kolekcji albo wymiar wektora
    """
    table_name, collection_name = docs_index_names(settings, synthetic)

    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    postgres = PostgresClient(
        host     = settings.postgres_host,
        port     = settings.postgres_port,
        database = settings.postgres_db,
        user     = settings.postgres_user,
        password = settings.postgres_password,
        timeout  = settings.postgres_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )

    indexer = DocsIndexer(
        embedder       = embedder,
        table          = DocsTable(postgres, name=table_name),
        collection     = DocsCollection(qdrant, collection_name, settings.embedding_vector_size),
        fragment_chars = settings.rag_docs_fragment_chars,
        synthetic      = synthetic,
    )

    return indexer
