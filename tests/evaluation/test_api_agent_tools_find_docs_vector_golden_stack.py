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

1. `measure_docs_vector()` z `tests/_helpers/synthetic_docs/` czyta 29 zapytań
   `find_docs_vector` z `data/safe/golden/docs-synthetic.json`: 24 ze wskazanymi sekcjami (część
   także z dystraktorami) i 5, na które poprawną odpowiedzią jest pusty wynik.
2. Każde wysyła do `FindDocsVectorTool` na indeksie syntetycznym, z `RAG_TOP_K`
   i `RAG_DOCS_SCORE_MIN` z konfiguracji.
3. Liczy trzy wielkości z tabelki, a testy porównują je z progami.

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

import pytest

from tests._helpers.synthetic_docs import (
    BUILD_HINT,
    MAX_UNANSWERED_WITH_HITS,
    MIN_DISTRACTORS_BELOW,
    MIN_EXPECTED_FIRST,
    DocsVectorMeasurement,
    measure_docs_vector,
)
from tests.conftest import build_host_settings

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


@pytest.fixture(scope="module")
def measurement(
    synthetic_docs_collection: None,  # warunek z conftest.py: kolekcja odpowiada plikom paczki
) -> DocsVectorMeasurement:
    """
    Description:
    Robi pomiar raz na cały plik: 29 wyszukań przez prawdziwy embedder. Najpierw warunek
    `synthetic_docs_collection` sprawdza, że indeks zbudowano dzisiejszym cięciem paczki —
    inaczej wynik byłby nieważny.

    Example args:
        synthetic_docs_collection=None

    Example result:
        DocsVectorMeasurement(expected_first=24, distractors_below=9, distractors_total=9,
                              unanswered_with_hits=1)
    """
    return asyncio.run(measure_docs_vector(build_host_settings()))


def test_the_expected_section_comes_back_first(measurement: DocsVectorMeasurement) -> None:
    """Sprawdza, czy wyszukiwanie w dokumentacji stawia właściwą sekcję na pierwszym miejscu: ma
    tak być dla co najmniej 22 z 24 zapytań, na które paczka ma odpowiedź.

    Wyłapuje pogorszenie wyszukiwania, przy którym nic nie pada, tylko wyniki są gorsze — na
    przykład po pomyleniu trybu embeddera, zmianie cięcia sekcji na fragmenty albo progu."""
    assert measurement.expected_first >= MIN_EXPECTED_FIRST, (
        f"oczekiwana sekcja wróciła pierwsza dla {measurement.expected_first} zapytań, oczekiwane "
        f">= {MIN_EXPECTED_FIRST} — czy indeks zbudowano przy dzisiejszym "
        f"`RAG_DOCS_FRAGMENT_CHARS` i czy zmieniło się `RAG_DOCS_SCORE_MIN`? {BUILD_HINT}"
    )


def test_a_section_about_another_channel_stays_below(measurement: DocsVectorMeasurement) -> None:
    """Sprawdza, czy sekcja o tym samym zagadnieniu, ale w innym kanale (np. ePUAP zamiast
    e-Doręczeń), stoi niżej niż sekcja właściwa: ma tak być w co najmniej 8 z 9 takich par.

    Wyłapuje wyszukiwanie, które myli bliźniacze sekcje — a rada z niewłaściwej bywa odwrotnością
    poprawnej."""
    assert measurement.distractors_below >= MIN_DISTRACTORS_BELOW, (
        f"niżej niż oczekiwana sekcja stoi {measurement.distractors_below} "
        f"z {measurement.distractors_total} dystraktorów, oczekiwane >= {MIN_DISTRACTORS_BELOW}"
    )


def test_questions_the_documentation_does_not_answer_mostly_come_back_empty(
    measurement: DocsVectorMeasurement,
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
