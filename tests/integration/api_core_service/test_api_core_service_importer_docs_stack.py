import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import NamedTuple

import pytest

from app.core_service.importer_docs import DocsImporter
from app.core_service.loader_doc_package import load_doc_package
from app.db_postgres import DocsTable
from app.db_qdrant import DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_host_settings, build_postgres_client, embedder_url, qdrant_url

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

# Co mieszka POZA naszym kodem i dlatego jest warte działających usług: że Postgres przyjmuje
# wiersze importu i oddaje je w kolejności dokumentów, że Qdrant przyjmuje punkty z wektorami
# prawdziwego embeddera, że sekcję da się potem znaleźć obiema drogami i że drugi import naprawdę
# zastępuje pierwszy. Kolejność kroków i odmowy sprawdza test jednostkowy na atrapach.
#
# Paczka jest mała i zmyślona, żeby test trwał sekundy; całą paczkę syntetyczną z repo sprawdza
# test ewaluacyjny na zbudowanym indeksie.

# Własny indeks, nigdy skonfigurowany: te testy KASUJĄ tabelę i kolekcję, których dotykają.
TABLE_NAME      = "docs_text_import_stack_test"
COLLECTION_NAME = "docs_import_stack_test"

# Mały limit, żeby trzy akapity sekcji `adm-zwierzeta` dały trzy fragmenty.
FRAGMENT_CHARS = 80

# Treści o trzech niezwiązanych tematach: asercja na ranking nie może zależeć od niuansu.
BODIES = {
    "adm-zwierzeta": (
        "Jednorożec mieszka w archiwum zakładowym i pilnuje teczek.\n\n"
        "Hipopotam odpowiada za podlewanie kwiatów w sekretariacie.\n\n"
        "Żyrafa wymienia żarówki w lampach pod sufitem.\n"
    ),
    "adm-kawa":      "Ekspres do kawy odkamienia się raz w miesiącu, w pierwszy poniedziałek.\n",
    "usr-parking":   "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej.\n",
}

DOCUMENTS = {
    "administrator": ("adm-zwierzeta", "adm-kawa"),
    "uzytkownik":    ("usr-parking",),
}


class Index(NamedTuple):
    """
    Description:
    Importer na prawdziwych usługach razem z tabelą i kolekcją testu — żeby test mógł i wgrać
    paczkę, i sprawdzić, co po niej zostało.
    """

    importer:   DocsImporter
    embedder:   EmbeddingClient
    table:      DocsTable
    collection: DocsCollection


def _write_package(
    root:      Path,                                       # np. tmp_path / "pelna"
    documents: tuple[str, ...] = tuple(DOCUMENTS),         # które dokumenty wchodzą do paczki
) -> Path:
    """
    Description:
    Zakłada paczkę z wybranych zmyślonych dokumentów: katalog na dokument, w nim manifest
    i plik `.md` na sekcję.

    Example args:
        root=Path("/tmp/x/pelna")
        documents=("administrator", "uzytkownik")

    Example result:
        Path("/tmp/x/pelna") z katalogami administrator/ i uzytkownik/
    """
    for name in documents:
        directory = root / name
        directory.mkdir(parents=True)

        manifest = {
            "document":  f"Instrukcja {name}",
            "version":   "1.0",
            "date":      "2026-10-05",
            "synthetic": True,
            "sections":  [
                {
                    "section_id":   section_id,
                    "chapter_path": ["Biuro"],
                    "title":        f"Sekcja {section_id}",
                    "description":  "Zmyślona sekcja testu importu",
                }
                for section_id in DOCUMENTS[name]
            ],
        }

        (directory / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )

        for section_id in DOCUMENTS[name]:
            (directory / f"{section_id}.md").write_text(BODIES[section_id], encoding="utf-8")

    return root


@pytest.fixture
async def index() -> AsyncIterator[Index]:
    """
    Description:
    Oddaje importer piszący do własnej tabeli i kolekcji testu, na prawdziwym embedderze,
    Postgresie i Qdrancie. Tabela i kolekcja są kasowane przed testem i po nim: test przerwany
    w połowie zostawiłby stan, na którym następny sprawdzałby stare dane.

    Example args:
        (brak)

    Example result:
        Index(importer=DocsImporter(…), embedder=…, table=DocsTable(…), collection=…)
    """
    settings   = build_host_settings()
    embedder   = EmbeddingClient(
        base_url = embedder_url(),
        timeout  = settings.embedding_timeout_seconds,
    )
    table      = DocsTable(build_postgres_client(), name=TABLE_NAME)
    collection = DocsCollection(
        QdrantClient(base_url=qdrant_url(), timeout=10.0),
        COLLECTION_NAME,
        settings.embedding_vector_size,
    )
    importer = DocsImporter(
        embedder       = embedder,
        table          = table,
        collection     = collection,
        fragment_chars = FRAGMENT_CHARS,
        synthetic      = True,
    )

    await table.drop()
    await collection.drop()

    yield Index(importer=importer, embedder=embedder, table=table, collection=collection)

    await table.drop()
    await collection.drop()
    await importer.aclose()


async def test_the_import_writes_every_section_and_fragment(tmp_path: Path, index: Index) -> None:
    """Paczka z dwóch dokumentów → wiersz na sekcję w kolejności dokumentów i punkt na
    fragment: sekcja z trzech akapitów ma trzy."""
    report = await index.importer.run(load_doc_package(_write_package(tmp_path / "pelna")))

    listed = await index.table.list_all()

    assert report.sections  == 3
    assert report.fragments == 5
    assert [row.section_id for row in listed] == ["adm-zwierzeta", "adm-kawa", "usr-parking"]
    assert await index.collection.count()     == 5


async def test_the_whole_section_reads_back_verbatim(tmp_path: Path, index: Index) -> None:
    """Sekcja pocięta na fragmenty → z tabeli wraca cała, znak w znak jak w pliku."""
    await index.importer.run(load_doc_package(_write_package(tmp_path / "pelna")))

    rows = await index.table.read_by_id(["adm-zwierzeta"])

    assert rows[0].body == BODIES["adm-zwierzeta"]


async def test_an_imported_section_is_found_by_word_and_by_meaning(
    tmp_path: Path,
    index:    Index,
) -> None:
    """Zaimportowana sekcja → znajdują ją słowa w innej odmianie (Postgres) i zapytanie o to
    samo innymi słowami (Qdrant); obie drogi wskazują ten sam `section_id`."""
    await index.importer.run(load_doc_package(_write_package(tmp_path / "pelna")))

    # "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej."
    by_word = await index.table.words("recepcja miejsca parkingowego", limit=5)
    vector  = (await index.embedder.embed_query(["gdzie zarezerwować miejsce na parkingu"]))[0]
    by_mean = await index.collection.search(vector=vector, limit=5)

    assert [row.section_id for row in by_word] == ["usr-parking"]
    assert by_mean[0].section_id               == "usr-parking"


async def test_a_detail_from_the_last_paragraph_has_its_own_point(
    tmp_path: Path,
    index:    Index,
) -> None:
    """Zapytanie o szczegół z ostatniego akapitu długiej sekcji → pierwsze trafienie wskazuje tę
    sekcję: po to są fragmenty."""
    await index.importer.run(load_doc_package(_write_package(tmp_path / "pelna")))

    # "Żyrafa wymienia żarówki w lampach pod sufitem."
    vector = (await index.embedder.embed_query(["kto wymienia żarówki pod sufitem"]))[0]
    hits   = await index.collection.search(vector=vector, limit=5)

    assert hits[0].section_id == "adm-zwierzeta"


async def test_a_second_import_replaces_the_first(tmp_path: Path, index: Index) -> None:
    """Po paczce z dwóch dokumentów import paczki z jednym → w tabeli i kolekcji zostaje tylko
    on: sekcje i fragmenty usunięte z paczki nie mogą przeżyć importu."""
    await index.importer.run(load_doc_package(_write_package(tmp_path / "pelna")))
    await index.importer.run(
        load_doc_package(_write_package(tmp_path / "mniejsza", documents=("uzytkownik",)))
    )

    listed = await index.table.list_all()

    assert [row.section_id for row in listed] == ["usr-parking"]
    assert await index.collection.count()     == 1
