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
    """Sprawdza, czy indeks właściwy dostaje domyślną tabelę dokumentacji `docs_text` i kolekcję
    o nazwie z konfiguracji, tu `docs`.

    Wyłapuje dopisek albo inną nazwę przy indeksie właściwym: indeksacja pisałaby wtedy do innej
    tabeli i kolekcji niż te, z których odpowiada agent."""
    assert docs_index_names(_settings(), synthetic=False) == ("docs_text", "docs")


def test_the_synthetic_index_has_its_own_table_and_collection() -> None:
    """Sprawdza, czy indeks syntetyczny dostaje własną tabelę i własną kolekcję, obie z dopiskiem
    `_synthetic`: `docs_text_synthetic` i `docs_synthetic`.

    Wyłapuje indeks syntetyczny pod nazwami indeksu właściwego: zmyślona paczka dokumentacji
    trafiłaby do tabeli i kolekcji, z których odpowiada agent."""
    assert docs_index_names(_settings(), synthetic=True) == (
        "docs_text_synthetic",
        "docs_synthetic",
    )


def test_the_synthetic_collection_follows_the_configured_name() -> None:
    """Sprawdza, czy nazwa kolekcji syntetycznej powstaje z nazwy ustawionej w konfiguracji: przy
    kolekcji `instrukcje` indeks syntetyczny to `instrukcje_synthetic`.

    Wyłapuje nazwę kolekcji syntetycznej zaszytą na stałe: po zmianie nazwy kolekcji w konfiguracji
    indeks syntetyczny nadal nazywałby się `docs_synthetic`, czyli stałby obok kolekcji domyślnej,
    a nie obok ustawionej."""
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
    """Sprawdza, czy indekser zbudowany dla danego indeksu, właściwego albo syntetycznego, dostaje
    tabelę i kolekcję tego indeksu oraz tę samą flagę, którą potem porównuje z manifestami
    dokumentów.

    Wyłapuje fabrykę, która podaje nazwy jednego indeksu, a flagę drugiego: indekser przyjąłby wtedy
    zmyśloną paczkę do właściwego indeksu albo prawdziwą dokumentację do syntetycznego."""
    indexer = build_docs_indexer(_settings(), synthetic)

    try:
        assert indexer._table.name      == table
        assert indexer._collection.name == collection
        assert indexer._synthetic       is synthetic
    finally:
        await indexer.aclose()


async def test_the_fragment_length_comes_from_the_configuration() -> None:
    """Sprawdza, czy limit długości fragmentu w indekserze pochodzi z konfiguracji: przy
    `RAG_DOCS_FRAGMENT_CHARS` ustawionym na 800 indekser ma limit 800.

    Wyłapuje limit zaszyty w kodzie albo wzięty z innego pola: zmiana ustawienia nie zmieniałaby
    wtedy cięcia dokumentacji i nic by tego nie pokazało."""
    indexer = build_docs_indexer(_settings(rag_docs_fragment_chars=800), synthetic=False)

    try:
        assert indexer._fragment_chars == 800
    finally:
        await indexer.aclose()


def test_a_missing_postgres_password_is_refused_at_build() -> None:
    """Sprawdza, czy budowa indeksera bez hasła do bazy kończy się błędem konfiguracji
    `DbPostgresConfigError`, który wymienia zmienną `POSTGRES_PASSWORD`.

    Wyłapuje brak hasła wykryty za późno: błąd wyszedłby dopiero jako nieudane połączenie w środku
    indeksacji i nie mówiłby, którą zmienną trzeba ustawić."""
    with pytest.raises(DbPostgresConfigError, match="POSTGRES_PASSWORD"):
        build_docs_indexer(_settings(postgres_password=None), synthetic=False)
