"""
Description:
Test ewaluacyjny narzędzia `find_tickets_vector` na golden secie: czy narzędzie w konfiguracji,
z jaką jedzie produkt, oddaje agentowi zgłoszenie, o które pyta zapytanie, i czy na zapytania bez
odpowiednika w bazie nie oddaje nic. Wymaga działającego stacku z zaindeksowanym korpusem
odniesienia.

| co mierzy                                          | próg            | zmierzone dziś |
|----------------------------------------------------|-----------------|----------------|
| zapytania, na które rekord-cel wraca jako pierwszy | co najmniej 115 | 119 ze 126     |
| zapytania, na które rekord-cel w ogóle wraca       | co najmniej 123 | 126 ze 126     |
| dystraktory, które dostają choć jedno trafienie    | najwyżej 8      | 7 z 16         |

Po co: narzędzie składa się z kilku ogniw (tekst zapytania, tryb embeddera, wektor w Qdrancie,
próg) i każde da się zepsuć tak, że nic nie padnie. Wyszukiwanie dalej coś zwraca, tylko gorsze,
a testy jednostkowe i integracyjne na trzech zmyślonych zgłoszeniach tego nie pokażą.

Co się dzieje po drodze:

1. `measure_tickets_vector()` z `tests/_helpers/golden_tickets/` czyta zapytania
   z `data/unsafe/golden/tickets.json` (126, każde ze wskazanym
   rekordem-celem) i z `data/unsafe/golden/tickets-distractors.json` (16, bez odpowiednika
   w indeksie).
2. Każde wysyła do `FindTicketsVectorTool` polami `query_problem` i `query_symptoms`, na
   skonfigurowanej kolekcji, z `RAG_TOP_K` i `RAG_SCORE_MIN` z konfiguracji.
3. Liczy, ile razy rekord-cel wrócił jako pierwszy, ile razy wrócił w ogóle i ile dystraktorów
   dostało choć jedno trafienie.

O czym pamiętać przy zmianach:

- `query_problem` i `query_symptoms` napisano z samego `query_raw`, bez wglądu w rekord-cel. Nie
  wolno ich poprawiać pod wynik: zastępują zapytanie agenta do czasu pomiaru na prawdziwym modelu
  (p. 23).
- Indeksem jest skonfigurowana kolekcja, a nie własna, bo zbudowanie własnej z 200 artefaktów trwa
  na CPU ponad dwie i pół minuty. Pusta kolekcja wywala test; buduje ją
  `helpdesk tickets reindex data/unsafe/parsed/gpt-6.1-sol-golden200-v2`.
- Indeks i golden set to te same rekordy, więc liczby pilnują, że ścieżka się nie zepsuła,
  a skutecznością produktu nie są.
- Zmiana `RAG_SCORE_MIN` albo `RAG_TOP_K` przesuwa wszystkie trzy liczby. Co próg robi z każdym
  zapytaniem, pokazuje `python scripts/eval_threshold.py detail`.
- `data/` nie ma w repo (PII), więc bez golden setu test się pomija, a nie pada.
"""


import asyncio

import pytest

from tests._helpers.golden_tickets import (
    DISTRACTORS_FILE,
    GOLDEN_FILE,
    MAX_DISTRACTORS_WITH_HITS,
    MIN_TARGET_FIRST,
    MIN_TARGET_RETURNED,
    TicketsVectorMeasurement,
    measure_tickets_vector,
)
from tests.conftest import build_host_settings

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]


@pytest.fixture(scope="module")
def measurement() -> TicketsVectorMeasurement:
    """
    Description:
    Robi pomiar raz na cały plik: 142 wyszukania przez prawdziwy embedder to kilkadziesiąt sekund.
    Bez golden setu pomija testy, zamiast je wywalać.

    Example args:
        (brak)

    Example result:
        TicketsVectorMeasurement(target_first=119, target_returned=126, distractors_with_hits=7)
    """
    if not GOLDEN_FILE.is_file() or not DISTRACTORS_FILE.is_file():
        pytest.skip(f"brak golden setu ({GOLDEN_FILE.parent}) — dane nie są w repo")

    return asyncio.run(measure_tickets_vector(build_host_settings()))


def test_the_expected_ticket_comes_back_first(measurement: TicketsVectorMeasurement) -> None:
    """Sprawdza, czy wyszukiwanie zgłoszeń stawia właściwe zgłoszenie na pierwszym miejscu: ma
    tak być dla co najmniej 115 ze 126 zapytań zestawu.

    Wyłapuje pogorszenie wyszukiwania, przy którym nic nie pada, tylko wyniki są gorsze — na
    przykład po pomyleniu trybu embeddera albo po zmianie tekstu, z którego liczy się wektor."""
    assert measurement.target_first >= MIN_TARGET_FIRST, (
        f"rekord-cel wrócił jako pierwszy dla {measurement.target_first} zapytań, oczekiwane >= "
        f"{MIN_TARGET_FIRST} — czy indeks stoi na korpusie odniesienia i czy zapytanie idzie "
        f"trybem query po wektorach `problem`?"
    )


def test_the_expected_ticket_survives_the_limit_and_the_threshold(
    measurement: TicketsVectorMeasurement,
) -> None:
    """Sprawdza, czy właściwe zgłoszenie w ogóle jest wśród zwróconych: ma tak być dla co
    najmniej 123 ze 126 zapytań zestawu.

    Wyłapuje próg podobieństwa albo limit trafień ustawiony tak, że odcina zgłoszenie, którego
    agent szuka."""
    assert measurement.target_returned >= MIN_TARGET_RETURNED, (
        f"rekord-cel wrócił dla {measurement.target_returned} zapytań, oczekiwane >= "
        f"{MIN_TARGET_RETURNED} — czy zmieniło się `RAG_SCORE_MIN` albo `RAG_TOP_K`?"
    )


def test_queries_without_a_match_mostly_come_back_empty(
    measurement: TicketsVectorMeasurement,
) -> None:
    """Sprawdza, czy na pytania, na które baza nie ma odpowiedzi, wyszukiwanie nie oddaje nic:
    jakiekolwiek zgłoszenie wolno dostać najwyżej 8 z 16 takich zapytań.

    Wyłapuje próg podobieństwa ustawiony za nisko, przy którym agent dostaje zgłoszenia bez
    związku ze sprawą — a one wyglądają na odpowiedź."""
    assert measurement.distractors_with_hits <= MAX_DISTRACTORS_WITH_HITS, (
        f"trafienie dostało {measurement.distractors_with_hits} dystraktorów, dozwolone "
        f"{MAX_DISTRACTORS_WITH_HITS} — próg przepuszcza zgłoszenia bez związku z zapytaniem"
    )
