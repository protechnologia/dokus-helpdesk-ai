import pytest

from app.config import Settings
from app.core_service.factory_docs_indexer import build_docs_indexer, docs_index_names
from app.db_postgres import DbPostgresConfigError

# Fabryka indeksera dokumentacji: który indeks dostaje które nazwy i z czego indekser powstaje.
# Bez usług — budowa klientów z nikim się nie łączy.


def _settings(
    **overrides: object,  # np. qdrant_docs_collection="instrukcje"
) -> Settings:
    """
    Description:
    Konfiguracja niezależna od `.env` i powłoki w polach, które czyta fabryka: wartości podane
    wprost wygrywają ze środowiskiem.

    Example args:
        overrides={"qdrant_docs_collection": "instrukcje"}

    Example result:
        Settings(qdrant_docs_collection="instrukcje", postgres_password="helpdesk", …)
    """
    values = {
        "qdrant_docs_collection":  "docs",
        "postgres_password":       "helpdesk",
        "rag_docs_fragment_chars": 1500,
        **overrides,
    }

    return Settings(_env_file=None, **values)


# --- nazwy indeksów -----------------------------------------------------------------------

def test_the_proper_index_takes_the_configured_collection() -> None:
    """Indeks właściwy → domyślna tabela dokumentacji i kolekcja z konfiguracji."""
    assert docs_index_names(_settings(), synthetic=False) == ("docs_text", "docs")


def test_the_synthetic_index_has_its_own_table_and_collection() -> None:
    """Indeks syntetyczny → obie nazwy z dopiskiem: paczka zmyślona nie ma jak trafić do
    tabeli ani kolekcji, z których odpowiada agent."""
    assert docs_index_names(_settings(), synthetic=True) == (
        "docs_text_synthetic",
        "docs_synthetic",
    )


def test_the_synthetic_collection_follows_the_configured_name() -> None:
    """Inna nazwa kolekcji w konfiguracji → indeks syntetyczny stoi obok niej, nie obok
    domyślnej."""
    names = docs_index_names(_settings(qdrant_docs_collection="instrukcje"), synthetic=True)

    assert names == ("docs_text_synthetic", "instrukcje_synthetic")


# --- budowa indeksera ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "synthetic, table, collection",
    [
        pytest.param(False, "docs_text",           "docs",           id="właściwy"),
        pytest.param(True,  "docs_text_synthetic", "docs_synthetic", id="syntetyczny"),
    ],
)
async def test_the_importer_writes_to_the_index_it_was_built_for(
    synthetic:  bool,
    table:      str,
    collection: str,
) -> None:
    """Flaga indeksu → indekser z tabelą i kolekcją tego indeksu i z tą samą flagą, którą
    sprawdza manifesty."""
    indexer = build_docs_indexer(_settings(), synthetic)

    try:
        assert indexer._table.name      == table
        assert indexer._collection.name == collection
        assert indexer._synthetic       is synthetic
    finally:
        await indexer.aclose()


async def test_the_fragment_length_comes_from_the_configuration() -> None:
    """`RAG_DOCS_FRAGMENT_CHARS` → limit długości fragmentu w indekserze."""
    indexer = build_docs_indexer(_settings(rag_docs_fragment_chars=800), synthetic=False)

    try:
        assert indexer._fragment_chars == 800
    finally:
        await indexer.aclose()


def test_a_missing_postgres_password_is_refused_at_build() -> None:
    """Brak hasła do bazy → błąd konfiguracji przy budowie, nie błąd połączenia w środku
    indeksacji."""
    with pytest.raises(DbPostgresConfigError, match="POSTGRES_PASSWORD"):
        build_docs_indexer(_settings(postgres_password=None), synthetic=False)
