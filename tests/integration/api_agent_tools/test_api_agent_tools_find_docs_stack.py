"""
Description:
Test integracyjny narzędzi `find_docs_vector` i `find_docs_text` z prawdziwym embedderem, Qdrantem
i Postgresem: czy to, co zapisuje indeksacja dokumentacji, da się znaleźć oboma narzędziami pod
tym samym identyfikatorem sekcji. Wymaga działającego stacku.

| narzędzie          | scenariusz                                | oczekiwanie                 |
|--------------------|-------------------------------------------|-----------------------------|
| `find_docs_vector` | pytanie innymi słowami niż sekcja         | ta sekcja pierwsza          |
| `find_docs_vector` | sekcja z trzech fragmentów                | wraca raz, obok pozostałych |
| `find_docs_text`   | słowa w innej odmianie niż w treści       | sekcja znaleziona słowami   |
| `find_docs_text`   | komunikat złamany w treści między liniami | sekcja znaleziona frazą     |
| `find_docs_text`   | fraza i słowa trafiające w różne sekcje   | obie, ta z frazy pierwsza   |
| oba                | ta sama sekcja znaleziona dwiema drogami  | ten sam opis sekcji         |

Co się dzieje po drodze:

1. Fixture kasuje tabelę i kolekcję testu i indeksuje trzy zmyślone sekcje produkcyjnym
   `DocsIndexer`: prawdziwy embedder liczy wektory fragmentów, Qdrant i Postgres je zapisują.
2. Testy pytają narzędzia zbudowane na tej samej tabeli i kolekcji.
3. Po teście tabela i kolekcja są kasowane, a połączenia zamykane.

O czym pamiętać przy zmianach:

- Tabela i kolekcja są własne (`*_find_stack_test`), nigdy skonfigurowane — test je kasuje.
- Asercje są na ranking i na to, co wróciło, nigdy na wysokość podobieństwa; próg jest wyłączony.
- Tryb embeddera, grupowanie, liczenie progu i limitu sprawdzają testy jednostkowe na
  podmienionym transporcie; trafność na całej paczce syntetycznej to sprawa testów ewaluacyjnych.
"""

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest

from app.agent_tools.docs.find_docs_text import FindDocsTextQuery, FindDocsTextTool
from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery, FindDocsVectorTool
from app.config import Settings
from app.core_model.docs.doc_directory import DocDirectory
from app.core_model.docs.doc_manifest import DocManifest
from app.core_model.docs.doc_manifest_section import DocManifestSection
from app.core_model.docs.doc_package import DocPackage
from app.core_service.indexer_docs import DocsIndexer
from app.db_postgres import DocsTable
from app.db_qdrant import DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_postgres_client

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_postgres,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

# Własny indeks, nigdy skonfigurowany — patrz opis modułu.
TABLE_NAME      = "docs_text_find_stack_test"
COLLECTION_NAME = "docs_find_stack_test"

# Mały limit, żeby trzy akapity sekcji `adm-zwierzeta` dały trzy fragmenty.
FRAGMENT_CHARS = 80

# Treści o trzech niezwiązanych tematach: asercja na ranking nie może zależeć od niuansu.
# W sekcji o ekspresie komunikat jest złamany między liniami, jak w pliku zawiniętym na szerokość.
BODIES = {
    "adm-zwierzeta": (
        "Jednorożec mieszka w archiwum zakładowym i pilnuje teczek.\n\n"
        "Hipopotam odpowiada za podlewanie kwiatów w sekretariacie.\n\n"
        "Żyrafa wymienia żarówki w lampach pod sufitem.\n"
    ),
    "adm-kawa": (
        "Ekspres do kawy odkamienia się raz w miesiącu. Na wyświetlaczu pojawia się wtedy\n"
        "komunikat „Uruchom program\n"
        "odkamieniania”, kod KAW-17.\n"
    ),
    "usr-parking": "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej.\n",
}


class Tools(NamedTuple):
    """
    Description:
    Oba narzędzia wyszukiwania dokumentacji na indeksie testu.
    """

    vector: FindDocsVectorTool
    text:   FindDocsTextTool


def _package() -> DocPackage:
    """
    Description:
    Zmyślona paczka z jednym dokumentem i trzema sekcjami, zbudowana w pamięci — w kształcie,
    jaki oddaje czytnik paczki z dysku.

    Example args:
        (brak)

    Example result:
        DocPackage(directories=[DocDirectory(manifest=DocManifest(…), bodies={…})])
    """
    manifest = DocManifest(
        document  = "Instrukcja biura",
        version   = "1.0",
        date      = date(2026, 10, 5),
        synthetic = True,
        sections  = [
            DocManifestSection(
                section_id   = section_id,
                chapter_path = ["Biuro"],
                title        = f"Sekcja {section_id}",
                description  = "Zmyślona sekcja testu narzędzi",
            )
            for section_id in BODIES
        ],
    )
    package = DocPackage(
        path        = Path("pamiec"),
        directories = [DocDirectory(path=Path("pamiec/biuro"), manifest=manifest, bodies=BODIES)],
    )

    return package


@pytest.fixture
async def tools(host_settings: Settings) -> AsyncIterator[Tools]:
    """
    Description:
    Oddaje oba narzędzia na własnej tabeli i kolekcji testu, zaindeksowanych produkcyjną ścieżką
    (`DocsIndexer`) — narzędzia mają znaleźć to, co naprawdę zapisuje indeksacja. Tabela
    i kolekcja są kasowane przed testem i po nim: przerwany przebieg nie zostawi starego stanu
    następnemu.

    Example args:
        host_settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        Tools(vector=FindDocsVectorTool(…), text=FindDocsTextTool(…))
    """
    embedder = EmbeddingClient(
        base_url = host_settings.embedding_base_url,
        timeout  = host_settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = host_settings.qdrant_url,
        timeout  = host_settings.qdrant_timeout_seconds,
    )
    table      = DocsTable(build_postgres_client(), name=TABLE_NAME)
    collection = DocsCollection(qdrant, COLLECTION_NAME, host_settings.embedding_vector_size)
    indexer = DocsIndexer(
        embedder       = embedder,
        table          = table,
        collection     = collection,
        fragment_chars = FRAGMENT_CHARS,
        synthetic      = True,
    )

    await indexer.rebuild(_package())

    yield Tools(
        # Próg wyłączony: na trzech sekcjach sprawdzamy kolejność, nie odcinanie.
        vector = FindDocsVectorTool(embedder=embedder, docs=collection, top_k=5, score_min=-1.0),
        text   = FindDocsTextTool(docs=table, limit=5),
    )

    await table.drop()
    await collection.drop()
    await indexer.aclose()


async def test_a_question_in_other_words_finds_the_section_first(tools: Tools) -> None:
    """Pytanie innymi słowami niż treść sekcji → ta sekcja na pierwszym miejscu. Asercja na
    ranking, nie na wysokość podobieństwa."""
    # "Miejsce parkingowe rezerwuje się w recepcji najpóźniej dzień wcześniej."
    result = await tools.vector.find(FindDocsVectorQuery(text="gdzie zarezerwować parking"))

    assert result.sections[0].section.section_id == "usr-parking"


async def test_a_section_of_several_fragments_comes_back_once(tools: Tools) -> None:
    """Sekcja pocięta na trzy fragmenty → w wyniku raz, a pozostałe sekcje obok niej: jednostką
    wyniku jest sekcja, którą da się odczytać, nie fragment."""
    # "Żyrafa wymienia żarówki w lampach pod sufitem."
    result = await tools.vector.find(FindDocsVectorQuery(text="kto wymienia żarówki pod sufitem"))
    found  = [item.section.section_id for item in result.sections]

    assert found[0]      == "adm-zwierzeta"
    assert sorted(found) == sorted(BODIES)


async def test_words_in_another_form_find_the_section(tools: Tools) -> None:
    """Słowa w innej odmianie niż w treści → sekcja znaleziona słowami: odmianę zna słownik bazy,
    nie nasz kod."""
    # "Hipopotam odpowiada za podlewanie kwiatów w sekretariacie."
    result = await tools.text.find(FindDocsTextQuery(words="hipopotamy kwiaty"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-zwierzeta", "words"),
    ]
    assert result.omitted_over_limit == 0


async def test_a_message_broken_across_lines_is_found_as_a_phrase(tools: Tools) -> None:
    """Komunikat złamany w treści po „Uruchom program" → fraza w jednej linii go znajduje,
    także inną wielkością liter."""
    result = await tools.text.find(FindDocsTextQuery(exact="uruchom program odkamieniania"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa", "exact"),
    ]


async def test_a_phrase_and_words_bring_their_own_sections(tools: Tools) -> None:
    """Fraza z jednej sekcji i słowa z innej → obie sekcje, znaleziona frazą pierwsza: pola
    szukają niezależnie, a wyniki się sumują."""
    result = await tools.text.find(FindDocsTextQuery(exact="KAW-17", words="recepcje parkingowe"))

    assert [(item.section.section_id, item.matched_by) for item in result.sections] == [
        ("adm-kawa",    "exact"),
        ("usr-parking", "words"),
    ]


async def test_both_tools_describe_a_section_the_same_way(tools: Tools) -> None:
    """Ta sama sekcja znaleziona po znaczeniu i po słowach → ten sam opis z metryczki: oba
    indeksy mają wskazywać jeden identyfikator, który potem przyjmie odczyt."""
    by_meaning = await tools.vector.find(FindDocsVectorQuery(text="gdzie zarezerwować parking"))
    by_words   = await tools.text.find(FindDocsTextQuery(words="miejsce parkingowe"))

    assert by_meaning.sections[0].section == by_words.sections[0].section
