"""
Description:
Test ewaluacyjny narzędzia `find_docs_vector` na zestawie zapytań paczki syntetycznej: czy
narzędzie w konfiguracji, z jaką jedzie produkt, stawia właściwą sekcję na pierwszym miejscu
i czy na zapytania, których dokumentacja nie opisuje, nie oddaje nic. Wymaga działającego stacku
z zaindeksowaną paczką.

| co mierzy                                             | próg           | zmierzone dziś |
|-------------------------------------------------------|----------------|----------------|
| zapytania z odpowiedzią: oczekiwana sekcja pierwsza   | co najmniej 22 | 24 z 24        |
| dystraktory stojące niżej niż najlepsza oczekiwana    | co najmniej 8  | 9 z 9          |
| zapytania bez odpowiedzi, które dostają jakąś sekcję  | najwyżej 2     | 1 z 5          |

Po co: narzędzie składa się z kilku ogniw (tryb embeddera, wektor w Qdrancie, grupowanie
fragmentów w sekcje, próg) i każde da się zepsuć tak, że nic nie padnie. Wyszukiwanie dalej coś
zwraca, tylko gorsze, a testy jednostkowe i integracyjne na trzech zmyślonych sekcjach tego nie
pokażą.

Co się dzieje po drodze:

1. Czyta 29 zapytań `find_docs_vector` z `data/safe/golden/docs-synthetic.json`: 24 ze wskazanymi
   sekcjami (część także z dystraktorami) i 5, na które poprawną odpowiedzią jest pusty wynik.
2. Każde wysyła do `FindDocsVectorTool` na indeksie syntetycznym, z `RAG_TOP_K`
   i `RAG_DOCS_SCORE_MIN` z konfiguracji.
3. Liczy trzy wielkości z tabelki.

O czym pamiętać przy zmianach:

- Zapytań nie wolno poprawiać pod wynik: pisano je tak, jak opis narzędzia każe pytać agentowi.
- Sekcje i zapytania pisał ten sam autor, więc liczby pilnują, że ścieżka się nie zepsuła,
  a skutecznością produktu nie są.
- Indeksem jest syntetyczny indeks z konfiguracji. Buduje go
  `docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes`; po
  zmianie `RAG_DOCS_FRAGMENT_CHARS` trzeba go zbudować ponownie.
- Przed pomiarem fixture `synthetic_docs_collection` z `conftest.py` sprawdza, że kolekcja ma
  tyle punktów, ile fragmentów daje dzisiejsze cięcie paczki; inny stan kończy pomiar błędem.
- Zmiana `RAG_DOCS_SCORE_MIN` przesuwa pierwszą i trzecią liczbę w przeciwne strony: przy 0.39
  wszystkie pięć zapytań bez odpowiedzi wraca pustych, ale jedno z 24 traci swoją sekcję.
"""

import asyncio
import json
from pathlib import Path
from typing import NamedTuple

import pytest

from app.agent_tools.docs.find_docs_vector import FindDocsVectorQuery, FindDocsVectorTool
from app.config import Settings
from app.core_service.factory_docs_indexer import docs_index_names
from app.db_qdrant import DbQdrantError, DocsCollection, QdrantClient
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_host_settings

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

GOLDEN_FILE = Path("data/safe/golden/docs-synthetic.json")

# Zmierzone 24 z 24; próg niżej, żeby wyłapać zepsutą ścieżkę, a nie zwykły dryf.
MIN_EXPECTED_FIRST = 22

# Zmierzone 9 z 9. Dystraktor to sekcja o tym samym zagadnieniu w innym kanale — postawiony
# wyżej odwraca radę.
MIN_DISTRACTORS_BELOW = 8

# Zmierzone 1 z 5: jedno zapytanie dostaje dwie sekcje tuż nad progiem.
MAX_UNANSWERED_WITH_HITS = 2

BUILD_HINT = (
    "zbuduj indeks syntetyczny: "
    "docker compose exec api helpdesk docs index data/safe/instruction --synthetic --yes"
)


class Measurement(NamedTuple):
    """
    Description:
    Wynik jednego przejścia zestawu przez narzędzie.
    """

    expected_first:       int  # zapytania z odpowiedzią, na które oczekiwana sekcja jest pierwsza
    distractors_below:    int  # dystraktory niżej niż najlepsza oczekiwana sekcja albo nieobecne
    distractors_total:    int  # wszystkie dystraktory zestawu
    unanswered_with_hits: int  # zapytania bez odpowiedzi z co najmniej jedną sekcją


def _queries() -> list[dict]:
    """
    Description:
    Czyta zapytania `find_docs_vector` z zestawu paczki syntetycznej.

    Example args:
        (brak)

    Example result:
        [{"id": "v01", "query": {"text": "…"}, "expected": ["adm-…"], "distractors": ["adm-…"]}, …]
    """
    return json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["find_docs_vector"]


async def _measure(
    settings: Settings,  # np. Settings(embedding_base_url="http://localhost:8001", …)
) -> Measurement:
    """
    Description:
    Przepuszcza zestaw przez `FindDocsVectorTool` zbudowane tak jak w produkcie, tylko na
    indeksie syntetycznym: `RAG_TOP_K` i `RAG_DOCS_SCORE_MIN` z konfiguracji. Indeks, którego nie
    ma, wywala test z podpowiedzią, jak go zbudować.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        Measurement(expected_first=24, distractors_below=9, distractors_total=9,
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
        for entry in _queries():
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

    measurement = Measurement(
        expected_first       = expected_first,
        distractors_below    = distractors_below,
        distractors_total    = distractors_total,
        unanswered_with_hits = unanswered_with_hits,
    )

    return measurement


@pytest.fixture(scope="module")
def measurement(
    synthetic_docs_collection: None,  # warunek z conftest.py: kolekcja odpowiada plikom paczki
) -> Measurement:
    """
    Description:
    Robi pomiar raz na cały plik: 29 wyszukań przez prawdziwy embedder. Najpierw warunek
    `synthetic_docs_collection` sprawdza, że indeks zbudowano dzisiejszym cięciem paczki —
    inaczej wynik byłby nieważny.

    Example args:
        synthetic_docs_collection=None

    Example result:
        Measurement(expected_first=24, distractors_below=9, distractors_total=9,
                    unanswered_with_hits=1)
    """
    return asyncio.run(_measure(build_host_settings()))


def test_the_expected_section_comes_back_first(measurement: Measurement) -> None:
    """Sprawdza, czy wyszukiwanie w dokumentacji stawia właściwą sekcję na pierwszym miejscu: ma
    tak być dla co najmniej 22 z 24 zapytań, na które paczka ma odpowiedź.

    Wyłapuje pogorszenie wyszukiwania, przy którym nic nie pada, tylko wyniki są gorsze — na
    przykład po pomyleniu trybu embeddera, zmianie cięcia sekcji na fragmenty albo progu."""
    assert measurement.expected_first >= MIN_EXPECTED_FIRST, (
        f"oczekiwana sekcja wróciła pierwsza dla {measurement.expected_first} zapytań, oczekiwane "
        f">= {MIN_EXPECTED_FIRST} — czy indeks zbudowano przy dzisiejszym "
        f"`RAG_DOCS_FRAGMENT_CHARS` i czy zmieniło się `RAG_DOCS_SCORE_MIN`? {BUILD_HINT}"
    )


def test_a_section_about_another_channel_stays_below(measurement: Measurement) -> None:
    """Sprawdza, czy sekcja o tym samym zagadnieniu, ale w innym kanale (np. ePUAP zamiast
    e-Doręczeń), stoi niżej niż sekcja właściwa: ma tak być w co najmniej 8 z 9 takich par.

    Wyłapuje wyszukiwanie, które myli bliźniacze sekcje — a rada z niewłaściwej bywa odwrotnością
    poprawnej."""
    assert measurement.distractors_below >= MIN_DISTRACTORS_BELOW, (
        f"niżej niż oczekiwana sekcja stoi {measurement.distractors_below} "
        f"z {measurement.distractors_total} dystraktorów, oczekiwane >= {MIN_DISTRACTORS_BELOW}"
    )


def test_questions_the_documentation_does_not_answer_mostly_come_back_empty(
    measurement: Measurement,
) -> None:
    """Sprawdza, czy na pytania, których dokumentacja nie opisuje, wyszukiwanie nie oddaje nic:
    jakąkolwiek sekcję wolno dostać najwyżej 2 z 5 takich zapytań.

    Wyłapuje próg podobieństwa ustawiony za nisko, przy którym agent dostaje sekcje bez związku
    z pytaniem zamiast informacji, że dokumentacja o tym milczy."""
    assert measurement.unanswered_with_hits <= MAX_UNANSWERED_WITH_HITS, (
        f"sekcję dostało {measurement.unanswered_with_hits} zapytań bez odpowiedzi, dozwolone "
        f"{MAX_UNANSWERED_WITH_HITS} — próg `RAG_DOCS_SCORE_MIN` przepuszcza sekcje bez związku "
        f"z zapytaniem"
    )
