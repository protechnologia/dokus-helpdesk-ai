"""
Description:
Test ewaluacyjny indeksacji dokumentacji na paczce syntetycznej: czy indeks syntetyczny na stacku
jest tym, co leży w `data/safe/instruction`, i czy fragmenty robią to, po co są. Wymaga
działającego stacku z zaindeksowaną paczką.

| co sprawdza                           | oczekiwanie                                 |
|---------------------------------------|---------------------------------------------|
| spis treści z tabeli                  | 27 sekcji w kolejności zestawu zapytań      |
| treść każdej sekcji                   | znak w znak jak plik `.md`                  |
| liczba punktów w kolekcji             | tyle, ile fragmentów daje dzisiejsze cięcie |
| szczegół z końca najdłuższej sekcji   | jej fragment w pierwszej piątce trafień     |

Po co: indeksacja składa się z kilku ogniw (czytnik paczki, cięcie, embedder, dwie bazy) i każde da
się zepsuć tak, że komenda dalej kończy się kodem 0. Testy integracyjne sprawdzają je na trzech
zmyślonych sekcjach; ten patrzy na całą paczkę, na której stoją pomiary narzędzi dokumentacji.

O czym pamiętać przy zmianach:

- Indeksem jest syntetyczny indeks z konfiguracji, a nie własny, bo policzenie wektorów całej
  paczki trwa na CPU ponad minutę. Buduje go
  `docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes`.
- Liczba punktów jest liczona tym samym cięciem i limitem co indeksacja, więc test pada, gdy indeks
  zbudowano przy innym `RAG_DOCS_FRAGMENT_CHARS` albo przed zmianą cięcia — wtedy wystarczy
  powtórzyć indeksację.
- Ostatni wiersz tabelki to jedyna asercja zależna od modelu embeddingowego. Przy jednym wektorze
  na sekcję celu nie było w pierwszej piątce; pierwsze miejsce i próg mierzy dopiero narzędzie
  `find_docs_vector` (CLAUDE.md -> p. 8).
"""

import asyncio
import json
from pathlib import Path
from typing import NamedTuple

import pytest

from app.config import Settings
from app.core_service.builder_doc_embedding_text import split_into_fragments
from app.core_service.factory_docs_indexer import docs_index_names
from app.db_postgres import DbPostgresError, DocsTable
from app.db_qdrant import DbQdrantError, DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_host_settings, build_postgres_client

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

PACKAGE     = Path("data/safe/instruction")
GOLDEN_FILE = Path("data/safe/golden/docs-synthetic.json")

# Zapytanie zestawu o szczegół z dwóch ostatnich linii najdłuższej sekcji paczki.
TAIL_QUERY_ID = "v24"

BUILD_HINT = (
    "zbuduj indeks syntetyczny: "
    "docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes"
)


class IndexState(NamedTuple):
    """
    Description:
    To, co test odczytał z indeksu syntetycznego jednym przebiegiem.
    """

    listed:    list[str]       # identyfikatory sekcji w kolejności spisu treści
    bodies:    dict[str, str]  # treść każdej sekcji, po identyfikatorze
    points:    int             # liczba punktów w kolekcji
    tail_hits: list[str]       # sekcje pięciu pierwszych trafień zapytania o koniec sekcji


def _golden() -> dict:
    """
    Description:
    Czyta zestaw zapytań paczki syntetycznej.

    Example args:
        (brak)

    Example result:
        {"meta": {…}, "list_docs": {…}, "find_docs_vector": […], …}
    """
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))


def _tail_query() -> dict:
    """
    Description:
    Wyjmuje z zestawu zapytanie o szczegół z końca najdłuższej sekcji.

    Example args:
        (brak)

    Example result:
        {"id": "v24", "query": {"text": "kto może opatrzyć…"}, "expected": ["adm-wykaz-…"], …}
    """
    entry = next(e for e in _golden()["find_docs_vector"] if e["id"] == TAIL_QUERY_ID)

    return entry


async def _read_index(
    settings: Settings,  # np. Settings(embedding_base_url="http://localhost:8001", …)
) -> IndexState:
    """
    Description:
    Czyta indeks syntetyczny: spis treści i treść z tabeli, liczbę punktów z kolekcji i trafienia
    jednego zapytania. Indeks, którego nie ma, wywala test z podpowiedzią, jak go zbudować.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        IndexState(listed=["adm-kancelaria-edoreczenia", …], bodies={…}, points=47, tail_hits=[…])
    """
    table_name, collection_name = docs_index_names(settings, synthetic=True)

    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    postgres   = build_postgres_client()
    table      = DocsTable(postgres, name=table_name)
    collection = DocsCollection(qdrant, collection_name, settings.embedding_vector_size)

    try:
        rows   = await table.list_all()
        points = await collection.count()
        vector = (await embedder.embed_query([_tail_query()["query"]["text"]]))[0]
        hits   = await collection.search(vector=vector, limit=5)
    except (DbPostgresError, DbQdrantError) as exc:
        # Brak tabeli albo kolekcji wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")
    finally:
        await embedder.aclose()
        await qdrant.aclose()
        await postgres.aclose()

    state = IndexState(
        listed    = [row.section_id for row in rows],
        bodies    = {row.section_id: row.body for row in rows},
        points    = points,
        tail_hits = [hit.section_id for hit in hits],
    )

    return state


@pytest.fixture(scope="module")
def settings() -> Settings:
    """
    Description:
    Konfiguracja z adresami usług dostępnymi z hosta, jedna na cały plik.

    Example args:
        (brak)

    Example result:
        Settings(embedding_base_url="http://localhost:8001", qdrant_url="http://localhost:6333", …)
    """
    return build_host_settings()


@pytest.fixture(scope="module")
def index(settings: Settings) -> IndexState:
    """
    Description:
    Czyta indeks raz na cały plik.

    Example args:
        settings=Settings(…)

    Example result:
        IndexState(listed=[…], bodies={…}, points=47, tail_hits=[…])
    """
    return asyncio.run(_read_index(settings))


def test_the_index_lists_the_package_in_document_order(index: IndexState) -> None:
    """Spis treści z tabeli → dokładnie sekcje paczki, w kolejności, której oczekuje zestaw."""
    assert index.listed == _golden()["list_docs"]["expected_section_ids"], BUILD_HINT


def test_every_section_reads_back_verbatim(index: IndexState) -> None:
    """Treść każdej sekcji z tabeli → znak w znak jak jej plik `.md`."""
    files = {path.stem: path.read_text(encoding="utf-8") for path in PACKAGE.glob("*/*.md")}

    assert index.bodies == files, BUILD_HINT


def test_the_collection_holds_one_point_per_fragment(
    index:    IndexState,
    settings: Settings,
) -> None:
    """Liczba punktów w kolekcji → tyle, ile fragmentów daje dzisiejsze cięcie paczki przy
    skonfigurowanym limicie: indeks nie jest sprzed zmiany cięcia ani limitu."""
    limit    = settings.rag_docs_fragment_chars
    expected = sum(
        len(split_into_fragments(path.read_text(encoding="utf-8"), limit))
        for path in PACKAGE.glob("*/*.md")
    )

    assert index.points == expected, BUILD_HINT


def test_a_detail_from_the_end_of_the_long_section_is_within_reach(index: IndexState) -> None:
    """Zapytanie o szczegół z dwóch ostatnich linii najdłuższej sekcji → jej fragment
    w pierwszej piątce trafień; jeden wektor na całą sekcję tego nie dawał."""
    expected = _tail_query()["expected"][0]

    assert expected in index.tail_hits
