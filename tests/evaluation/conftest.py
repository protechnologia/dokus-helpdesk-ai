"""
Description:
Warunki wstępne pomiarów na paczce syntetycznej. Testy ewaluacyjne dokumentacji mierzą
wyszukiwanie na indeksie syntetycznym zbudowanym wcześniej na stacku; fixture'y stąd sprawdzają
przed pomiarem, że ten indeks odpowiada plikom paczki i dzisiejszej konfiguracji.

| fixture                     | co sprawdza                  | pyta     | pomiar             |
|-----------------------------|------------------------------|----------|--------------------|
| `synthetic_docs_table`      | sekcje paczki i ich treść    | Postgres | `find_docs_text`   |
| `synthetic_docs_collection` | punktów tyle, ile fragmentów | Qdrant   | `find_docs_vector` |

Tabela ma mieć dokładnie sekcje paczki, w kolejności ze spisu w zestawie zapytań, z treścią znak
w znak jak w plikach. Kolekcja ma mieć tyle punktów, na ile fragmentów tnie paczkę dzisiejsza
konfiguracja.

Po co: nieaktualny indeks nie znaczy „niska skuteczność", tylko „pomiar jest nieważny". Dlatego
to nie są testy z własnym wynikiem, tylko warunek pomiaru: gdy indeks nie odpowiada paczce,
pomiar kończy się błędem z podpowiedzią, jak indeks zbudować, zamiast podać liczby zmierzone na
czymś innym niż pliki.

Co się dzieje po drodze:

1. Fixture pomiaru (`results`, `measurement`) prosi o warunek swojej bazy.
2. Warunek czyta indeks syntetyczny z konfiguracji i porównuje go z plikami
   w `data/safe/instruction/`.
3. Różnica kończy pomiar błędem, który ją nazywa; zgodność przepuszcza pomiar dalej.

O czym pamiętać przy zmianach:

- Każdy warunek pyta tylko tę bazę, której używa jego pomiar: pomiar wyszukiwania tekstowego nie
  wymaga przez to Qdranta, a wyszukiwania po znaczeniu — Postgresa.
- Sama liczba punktów nie wykryje zmiany treści przy tej samej liczbie fragmentów. Wykrywa ją
  warunek tabeli, a tabelę i kolekcję buduje jedna komenda.
- Liczba fragmentów jest liczona tym samym cięciem i limitem co indeksacja, więc warunek pada, gdy
  indeks zbudowano przy innym `RAG_DOCS_FRAGMENT_CHARS` albo przed zmianą cięcia.
- Indeksem jest syntetyczny indeks z konfiguracji, a nie własny, bo policzenie wektorów całej
  paczki trwa na CPU ponad minutę.
"""

import asyncio
import json
from pathlib import Path

import pytest

from app.config import Settings
from app.core_service.builder_doc_embedding_text import split_into_fragments
from app.core_service.factory_docs_indexer import docs_index_names
from app.db_postgres import DbPostgresError, DocsTable
from app.db_qdrant import DbQdrantError, DocsCollection, QdrantClient
from tests.conftest import build_host_settings, build_postgres_client

PACKAGE     = Path("data/safe/instruction")
GOLDEN_FILE = Path("data/safe/golden/docs-synthetic.json")

BUILD_HINT = (
    "zbuduj indeks syntetyczny: "
    "docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes"
)


def _section_files() -> dict[str, str]:
    """
    Description:
    Czyta treść każdej sekcji paczki syntetycznej z jej pliku `.md`, po identyfikatorze sekcji.

    Example args:
        (brak)

    Example result:
        {"adm-kancelaria-edoreczenia": "Uprawnienie do kancelarii…", "usr-odswiezanie": "…", …}
    """
    return {path.stem: path.read_text(encoding="utf-8") for path in PACKAGE.glob("*/*.md")}


async def _table_differences(
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
    files    = _section_files()
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


async def _collection_differences(
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
        for body in _section_files().values()
    )

    if points == fragments:
        return []

    difference = (
        f"kolekcja ma {points} punktów, a dzisiejsze cięcie paczki daje {fragments} fragmentów"
    )

    return [difference]


def _require_no_differences(
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


@pytest.fixture(scope="module")
def synthetic_docs_table() -> None:
    """
    Description:
    Warunek pomiaru wyszukiwania tekstowego: tabela indeksu syntetycznego ma dokładnie sekcje
    paczki, w kolejności dokumentów, z treścią znak w znak jak w plikach. Tabela, której nie ma,
    i tabela nieaktualna kończą pomiar błędem z podpowiedzią, jak zbudować indeks.

    Example args:
        (brak)

    Example result:
        None — tabela odpowiada paczce
    """
    try:
        differences = asyncio.run(_table_differences(build_host_settings()))
    except DbPostgresError as exc:
        # Brak tabeli wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")

    _require_no_differences(differences)


@pytest.fixture(scope="module")
def synthetic_docs_collection() -> None:
    """
    Description:
    Warunek pomiaru wyszukiwania po znaczeniu: kolekcja indeksu syntetycznego ma tyle punktów, na
    ile fragmentów tnie paczkę dzisiejsza konfiguracja. Kolekcja, której nie ma, i kolekcja
    sprzed zmiany cięcia kończą pomiar błędem z podpowiedzią, jak zbudować indeks.

    Example args:
        (brak)

    Example result:
        None — kolekcja odpowiada paczce
    """
    try:
        differences = asyncio.run(_collection_differences(build_host_settings()))
    except DbQdrantError as exc:
        # Brak kolekcji wygląda jak błąd zapytania; podpowiedź mówi, co zrobić.
        pytest.fail(f"indeks syntetyczny nie odpowiada ({exc}) — {BUILD_HINT}")

    _require_no_differences(differences)
