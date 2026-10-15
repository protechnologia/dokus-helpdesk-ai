"""
Description:
Dokumentacja syntetyczna w testach ewaluacyjnych: zestaw zapytań do paczki, sprawdzenie, że indeks
syntetyczny na stacku odpowiada plikom paczki, i pomiary obu wyszukiwań w dokumentacji na tym
indeksie. Nieaktualny indeks nie znaczy „niska skuteczność”, tylko „pomiar jest nieważny”, więc
różnica kończy pomiar błędem z podpowiedzią, jak indeks zbudować.

| co                          | do czego                                                       |
|-----------------------------|----------------------------------------------------------------|
| `section_files()`           | treść każdej sekcji paczki z jej pliku `.md`                   |
| `table_differences()`       | różnice tabeli indeksu wobec paczki: skład, kolejność, treść   |
| `collection_differences()`  | różnica liczby punktów kolekcji wobec dzisiejszego cięcia      |
| `require_no_differences()`  | kończy pomiar błędem, gdy indeks różni się od paczki           |
| `docs_text_entries()`       | zapytania `find_docs_text` z zestawu                           |
| `search_docs_text()`        | wyniki `find_docs_text` na indeksie syntetycznym, po zapytaniu |
| `docs_vector_entries()`     | zapytania `find_docs_vector` z zestawu                         |
| `measure_docs_vector()`     | pomiar `find_docs_vector` na indeksie syntetycznym             |

Co się dzieje po drodze:

1. Fixture warunku z `tests/evaluation/conftest.py` porównuje indeks z plikami paczki — tabelę
   (`table_differences()`) albo kolekcję (`collection_differences()`) — i różnicę zamienia
   w błąd (`require_no_differences()`).
2. Fixture pomiaru przepuszcza zapytania zestawu przez narzędzie zbudowane tak jak w produkcie,
   tylko na indeksie syntetycznym.

O czym pamiętać przy zmianach:

- Każdy warunek pyta tylko tę bazę, której używa jego pomiar: pomiar wyszukiwania tekstowego nie
  wymaga przez to Qdranta, a wyszukiwania po znaczeniu — Postgresa.
- Sama liczba punktów nie wykryje zmiany treści przy tej samej liczbie fragmentów. Wykrywa ją
  warunek tabeli, a tabelę i kolekcję buduje jedna komenda.
- Liczba fragmentów jest liczona tym samym cięciem i limitem co indeksacja, więc warunek pada,
  gdy indeks zbudowano przy innym `RAG_DOCS_FRAGMENT_CHARS` albo przed zmianą cięcia.
- Indeksem jest syntetyczny indeks z konfiguracji, a nie własny, bo policzenie wektorów całej
  paczki trwa na CPU ponad minutę.
"""

import json
from typing import Any

import pytest

from app.agent_tools.docs.find_docs_text import (
    FindDocsTextQuery,
    FindDocsTextResult,
    FindDocsTextTool,
)
from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery, FindDocsVectorTool
from app.config import Settings
from app.core_service.builder_doc_embedding_text import split_into_fragments
from app.core_service.factory_docs_indexer import docs_index_names
from app.db_postgres import DbPostgresError, DocsTable
from app.db_qdrant import DbQdrantError, DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests._helpers.synthetic_docs.constants import BUILD_HINT, GOLDEN_FILE, PACKAGE_DIR
from tests._helpers.synthetic_docs.models.docs_vector_measurement import DocsVectorMeasurement
from tests.conftest import build_postgres_client


def section_files() -> dict[str, str]:
    """
    Description:
    Czyta treść każdej sekcji paczki syntetycznej z jej pliku `.md`, po identyfikatorze sekcji.

    Example args:
        (brak)

    Example result:
        {"adm-kancelaria-edoreczenia": "Uprawnienie do kancelarii…", "usr-odswiezanie": "…", …}
    """
    return {path.stem: path.read_text(encoding="utf-8") for path in PACKAGE_DIR.glob("*/*.md")}


async def table_differences(
    settings: Settings,  # np. Settings(postgres_host="localhost", …)
) -> list[str]:
    """
    Description:
    Porównuje tabelę indeksu syntetycznego z paczką: skład i kolejność sekcji ze spisem z zestawu
    zapytań, a treść każdej sekcji z jej plikiem. Oddaje opisy różnic; pusta lista znaczy, że
    tabela odpowiada paczce.

    Example args:
        settings=Settings(postgres_host="localhost", …)

    Example result:
        ["treść różni się od pliku w sekcjach: usr-odswiezanie"]

    Raises:
        DbPostgresError: tabeli nie ma albo baza nie odpowiada
    """
    table_name, _ = docs_index_names(settings, synthetic=True)
    table         = DocsTable(build_postgres_client(), name=table_name)

    try:
        rows = await table.list_all()
    finally:
        await table.aclose()

    golden   = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    expected = golden["list_docs"]["expected_section_ids"]
    files    = section_files()
    listed   = [row.section_id for row in rows]

    differences: list[str] = []

    # --- skład i kolejność spisu ---
    if listed != expected:
        differences.append(
            f"spis ma {len(listed)} sekcji w innym składzie albo kolejności niż paczka "
            f"({len(expected)})"
        )

    # --- treść znak w znak ---
    changed = sorted(row.section_id for row in rows if files.get(row.section_id) != row.body)

    if changed:
        differences.append(f"treść różni się od pliku w sekcjach: {', '.join(changed)}")

    return differences


async def collection_differences(
    settings: Settings,  # np. Settings(qdrant_url="http://localhost:6333", …)
) -> list[str]:
    """
    Description:
    Porównuje liczbę punktów w kolekcji indeksu syntetycznego z liczbą fragmentów, na które
    dzisiejsze cięcie i limit dzielą pliki paczki. Oddaje opis różnicy; pusta lista znaczy, że
    kolekcja odpowiada paczce.

    Example args:
        settings=Settings(qdrant_url="http://localhost:6333", rag_docs_fragment_chars=1000, …)

    Example result:
        ["kolekcja ma 41 punktów, a dzisiejsze cięcie paczki daje 58 fragmentów"]

    Raises:
        DbQdrantError: kolekcji nie ma albo Qdrant nie odpowiada
    """
    _, collection_name = docs_index_names(settings, synthetic=True)

    qdrant     = QdrantClient(base_url=settings.qdrant_url, timeout=settings.qdrant_timeout_seconds)
    collection = DocsCollection(qdrant, collection_name, settings.embedding_vector_size)

    try:
        points = await collection.count()
    finally:
        await qdrant.aclose()

    fragments = sum(
        len(split_into_fragments(body, settings.rag_docs_fragment_chars))
        for body in section_files().values()
    )

    if points == fragments:
        return []

    difference = (
        f"kolekcja ma {points} punktów, a dzisiejsze cięcie paczki daje {fragments} fragmentów"
    )

    return [difference]


def require_no_differences(
    differences: list[str],  # np. ["treść różni się od pliku w sekcjach: usr-odswiezanie"]
) -> None:
    """
    Description:
    Kończy pomiar błędem, gdy indeks różni się od paczki: liczby zmierzone na takim indeksie
    mówiłyby o czymś innym niż pliki.

    Example args:
        differences=[]

    Example result:
        None — indeks odpowiada paczce
    """
    if differences:
        pytest.fail(
            f"indeks syntetyczny nie odpowiada paczce, pomiar byłby nieważny: "
            f"{'; '.join(differences)} — {BUILD_HINT}"
        )


def docs_text_entries() -> list[dict[str, Any]]:
    """
    Description:
    Czyta zapytania `find_docs_text` z zestawu paczki syntetycznej: zapytanie w kształcie
    narzędzia i to, co ma wrócić.

    Example args:
        (brak)

    Example result:
        [{"id": "t01", "phenomenon": "…", "query": {"exact": "…"}, "expected": [{…}]}, …]
    """
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["find_docs_text"]


async def search_docs_text(
    settings: Settings,  # np. Settings(rag_top_k=5, …)
) -> dict[str, FindDocsTextResult]:
    """
    Description:
    Przepuszcza wszystkie zapytania `find_docs_text` z zestawu przez narzędzie na indeksie
    syntetycznym, z limitem z konfiguracji, i oddaje wyniki po identyfikatorze zapytania.
    Tabela, której nie ma, kończy pomiar błędem z podpowiedzią, jak ją zbudować.

    Example args:
        settings=Settings(rag_top_k=5, …)

    Example result:
        {"t01": FindDocsTextResult(sections=[MatchedSection(…)], omitted_over_limit=0), …}
    """
    table_name, _ = docs_index_names(settings, synthetic=True)

    tool = FindDocsTextTool(
        docs  = DocsTable(build_postgres_client(), name=table_name),
        limit = settings.rag_top_k,
    )

    try:
        results = {
            entry["id"]: await tool.find(FindDocsTextQuery(**entry["query"]))
            for entry in docs_text_entries()
        }
    except DbPostgresError as exc:
        # Brak tabeli wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")
    finally:
        await tool.aclose()

    return results


def docs_vector_entries() -> list[dict[str, Any]]:
    """
    Description:
    Czyta zapytania `find_docs_vector` z zestawu paczki syntetycznej.

    Example args:
        (brak)

    Example result:
        [{"id": "v01", "query": {"text": "…"}, "expected": ["adm-…"], "distractors": ["adm-…"]}, …]
    """
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["find_docs_vector"]


async def measure_docs_vector(
    settings: Settings,  # np. Settings(embedding_base_url="http://localhost:8001", …)
) -> DocsVectorMeasurement:
    """
    Description:
    Przepuszcza zapytania `find_docs_vector` z zestawu przez narzędzie zbudowane tak jak
    w produkcie, tylko na indeksie syntetycznym: `RAG_TOP_K` i `RAG_DOCS_SCORE_MIN`
    z konfiguracji. Indeks, którego nie ma, kończy pomiar błędem z podpowiedzią, jak go zbudować.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        DocsVectorMeasurement(expected_first=24, distractors_below=9, distractors_total=9,
                              unanswered_with_hits=1)
    """
    _, collection_name = docs_index_names(settings, synthetic=True)

    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    tool = FindDocsVectorTool(
        embedder  = embedder,
        docs      = DocsCollection(qdrant, collection_name, settings.embedding_vector_size),
        top_k     = settings.rag_top_k,
        score_min = settings.rag_docs_score_min,
    )

    expected_first       = 0
    distractors_below    = 0
    distractors_total    = 0
    unanswered_with_hits = 0

    try:
        for entry in docs_vector_entries():
            result = await tool.find(FindDocsVectorQuery(**entry["query"]))
            found  = [item.section.section_id for item in result.sections]

            # --- zapytanie bez odpowiedzi: każda zwrócona sekcja jest tu pomyłką ---
            if not entry["expected"]:
                unanswered_with_hits += bool(found)

                continue

            # --- zapytanie z odpowiedzią ---
            expected_first += found[:1] != [] and found[0] in entry["expected"]

            # Miejsce najlepszej oczekiwanej sekcji; gdy żadna nie wróciła, dystraktor nie ma
            # od czego stać niżej.
            places = [found.index(wanted) for wanted in entry["expected"] if wanted in found]

            for distractor in entry.get("distractors", []):
                distractors_total += 1
                distractors_below += bool(places) and (
                    distractor not in found or found.index(distractor) > min(places)
                )
    except DbQdrantError as exc:
        # Brak kolekcji wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")
    finally:
        await tool.aclose()

    measurement = DocsVectorMeasurement(
        expected_first       = expected_first,
        distractors_below    = distractors_below,
        distractors_total    = distractors_total,
        unanswered_with_hits = unanswered_with_hits,
    )

    return measurement
