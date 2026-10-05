"""
Description:
Test ewaluacyjny narzędzia `find_tickets_vector` na golden secie: czy narzędzie w konfiguracji,
z jaką jedzie produkt, oddaje agentowi zgłoszenie, o które pyta zapytanie, i czy na zapytania bez
odpowiednika w bazie nie oddaje nic. Wymaga działającego stacku z zaindeksowanym korpusem
odniesienia.

| co mierzy                                          | próg            | zmierzone dziś |
|----------------------------------------------------|-----------------|----------------|
| zapytania, na które rekord-cel wraca jako pierwszy | co najmniej 145 | 152 ze 162     |
| zapytania, na które rekord-cel w ogóle wraca       | co najmniej 155 | 160 ze 162     |
| dystraktory, które dostają choć jedno trafienie    | najwyżej 5      | 3 z 16         |

Po co: narzędzie składa się z kilku ogniw (tekst zapytania, tryb embeddera, wektor w Qdrancie,
próg) i każde da się zepsuć tak, że nic nie padnie. Wyszukiwanie dalej coś zwraca, tylko gorsze,
a testy jednostkowe i integracyjne na trzech zmyślonych zgłoszeniach tego nie pokażą.

Co się dzieje po drodze:

1. Czyta zapytania z `data/unsafe/golden/golden200.json` (162, każde ze wskazanym rekordem-celem)
   i z `data/unsafe/golden/distractors.json` (16, bez odpowiednika w indeksie).
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
  `helpdesk tickets index data/unsafe/parsed/bielik-11b-golden200`.
- Indeks i golden set to te same rekordy, więc liczby pilnują, że ścieżka się nie zepsuła,
  a skutecznością produktu nie są.
- Zmiana `RAG_SCORE_MIN` albo `RAG_TOP_K` przesuwa wszystkie trzy liczby. Co próg robi z każdym
  zapytaniem, pokazuje `python scripts/eval_threshold.py detail`.
- `data/` nie ma w repo (PII), więc bez golden setu test się pomija, a nie pada.
"""

import asyncio
import json
from pathlib import Path
from typing import NamedTuple

import pytest

from app.agent_tools.tickets.find_tickets_vector import (
    FindTicketsVectorQuery,
    FindTicketsVectorTool,
)
from app.config import Settings
from app.db_qdrant import QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_host_settings

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

# Zapytania z rekordem-celem i zapytania bez odpowiednika w indeksie.
GOLDEN_FILE      = Path("data/unsafe/golden/golden200.json")
DISTRACTORS_FILE = Path("data/unsafe/golden/distractors.json")

# Zmierzone 152 ze 162; próg niżej, żeby wyłapać zepsutą ścieżkę, a nie zwykły dryf.
MIN_TARGET_FIRST = 145

# Zmierzone 160 ze 162: jeden cel wypada poza pierwszą piątkę, jeden odcina próg.
MIN_TARGET_RETURNED = 155

# Zmierzone 3 z 16. Trafienie na zapytanie bez odpowiednika wygląda na odpowiedź, a nią nie jest.
MAX_DISTRACTORS_WITH_HITS = 5


class Measurement(NamedTuple):
    """
    Description:
    Wynik jednego przejścia golden setu i dystraktorów przez narzędzie.
    """

    target_first:          int  # zapytania, na które rekord-cel wrócił jako pierwszy
    target_returned:       int  # zapytania, na które rekord-cel wrócił na dowolnym miejscu
    distractors_with_hits: int  # dystraktory z co najmniej jednym trafieniem


def _load_golden_queries() -> list[tuple[str, FindTicketsVectorQuery]]:
    """
    Description:
    Czyta zapytania golden setu w kształcie narzędzia, każde w parze z id rekordu-celu.

    Example args:
        (brak)

    Example result:
        [("90001", FindTicketsVectorQuery(problem="Nie przychodzą przesyłki…", symptoms="…")), …]
    """
    golden  = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    queries = [
        (
            str(entry["expected_ticket_id"]),
            FindTicketsVectorQuery(
                problem  = entry["query_problem"],
                symptoms = entry["query_symptoms"],
            ),
        )
        for entry in golden["queries"]
    ]

    return queries


def _load_distractor_queries() -> list[FindTicketsVectorQuery]:
    """
    Description:
    Czyta dystraktory w kształcie narzędzia: zapytania, na które poprawną odpowiedzią jest pusta
    lista.

    Example args:
        (brak)

    Example result:
        [FindTicketsVectorQuery(problem="Nie drukuje się raport kasowy", symptoms="…"), …]
    """
    distractors = json.loads(DISTRACTORS_FILE.read_text(encoding="utf-8"))
    queries     = [
        FindTicketsVectorQuery(problem=entry["query_problem"], symptoms=entry["query_symptoms"])
        for entry in distractors["queries"]
    ]

    return queries


async def _measure(
    settings: Settings,  # np. Settings(embedding_base_url="http://localhost:8001", …)
) -> Measurement:
    """
    Description: Przepuszcza oba zestawy przez `FindTicketsVectorTool` zbudowane tak jak
    w produkcie: skonfigurowana kolekcja, `RAG_TOP_K` i `RAG_SCORE_MIN` z konfiguracji. Pustą
    kolekcję odrzuca od razu — inaczej wszystkie liczby wyszłyby zerowe i wyglądały na zepsute
    wyszukiwanie.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        Measurement(target_first=152, target_returned=160, distractors_with_hits=3)

    Raises:
        AssertionError: skonfigurowana kolekcja jest pusta
        EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        DbQdrantError: Qdrant jest nieosiągalny albo kolekcja nie istnieje
    """
    embedder = EmbeddingClient(
        base_url = settings.embedding_base_url,
        timeout  = settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = settings.qdrant_url,
        timeout  = settings.qdrant_timeout_seconds,
    )
    tickets = TicketsCollection(
        client      = qdrant,
        name        = settings.qdrant_collection,
        vector_size = settings.embedding_vector_size,
    )
    tool = FindTicketsVectorTool(
        embedder  = embedder,
        tickets   = tickets,
        top_k     = settings.rag_top_k,
        score_min = settings.rag_score_min,
    )

    try:
        # --- warunek wstępny: jest w czym szukać ---
        indexed = await tickets.count()

        assert indexed > 0, (
            f"kolekcja `{settings.qdrant_collection}` jest pusta — zbuduj indeks: "
            f"helpdesk tickets index data/unsafe/parsed/bielik-11b-golden200"
        )

        # --- zapytania z rekordem-celem ---
        target_first    = 0
        target_returned = 0

        for target, query in _load_golden_queries():
            result = await tool.find(query)
            found  = [item.ticket_id for item in result.tickets]

            target_first    += found[:1] == [target]
            target_returned += target in found

        # --- dystraktory: każde trafienie jest tu pomyłką ---
        distractors_with_hits = 0

        for query in _load_distractor_queries():
            result = await tool.find(query)

            distractors_with_hits += bool(result.tickets)
    finally:
        await tool.aclose()

    measurement = Measurement(
        target_first          = target_first,
        target_returned       = target_returned,
        distractors_with_hits = distractors_with_hits,
    )

    return measurement


@pytest.fixture(scope="module")
def measurement() -> Measurement:
    """
    Description:
    Robi pomiar raz na cały plik: 178 wyszukań przez prawdziwy embedder to kilkadziesiąt sekund.
    Bez golden setu pomija testy, zamiast je wywalać.

    Example args:
        (brak)

    Example result:
        Measurement(target_first=152, target_returned=160, distractors_with_hits=3)
    """
    if not GOLDEN_FILE.is_file() or not DISTRACTORS_FILE.is_file():
        pytest.skip(f"brak golden setu ({GOLDEN_FILE.parent}) — dane nie są w repo")

    return asyncio.run(_measure(build_host_settings()))


def test_the_expected_ticket_comes_back_first(measurement: Measurement) -> None:
    """Sprawdza, czy wyszukiwanie zgłoszeń stawia właściwe zgłoszenie na pierwszym miejscu: ma
    tak być dla co najmniej 145 ze 162 zapytań zestawu.

    Wyłapuje pogorszenie wyszukiwania, przy którym nic nie pada, tylko wyniki są gorsze — na
    przykład po pomyleniu trybu embeddera albo po zmianie tekstu, z którego liczy się wektor."""
    assert measurement.target_first >= MIN_TARGET_FIRST, (
        f"rekord-cel wrócił jako pierwszy dla {measurement.target_first} zapytań, oczekiwane >= "
        f"{MIN_TARGET_FIRST} — czy indeks stoi na korpusie odniesienia i czy zapytanie idzie "
        f"trybem query po wektorach `problem`?"
    )


def test_the_expected_ticket_survives_the_limit_and_the_threshold(
    measurement: Measurement,
) -> None:
    """Sprawdza, czy właściwe zgłoszenie w ogóle jest wśród zwróconych: ma tak być dla co
    najmniej 155 ze 162 zapytań zestawu.

    Wyłapuje próg podobieństwa albo limit trafień ustawiony tak, że odcina zgłoszenie, którego
    agent szuka."""
    assert measurement.target_returned >= MIN_TARGET_RETURNED, (
        f"rekord-cel wrócił dla {measurement.target_returned} zapytań, oczekiwane >= "
        f"{MIN_TARGET_RETURNED} — czy zmieniło się `RAG_SCORE_MIN` albo `RAG_TOP_K`?"
    )


def test_queries_without_a_match_mostly_come_back_empty(measurement: Measurement) -> None:
    """Sprawdza, czy na pytania, na które baza nie ma odpowiedzi, wyszukiwanie nie oddaje nic:
    jakiekolwiek zgłoszenie wolno dostać najwyżej 5 z 16 takich zapytań.

    Wyłapuje próg podobieństwa ustawiony za nisko, przy którym agent dostaje zgłoszenia bez
    związku ze sprawą — a one wyglądają na odpowiedź."""
    assert measurement.distractors_with_hits <= MAX_DISTRACTORS_WITH_HITS, (
        f"trafienie dostało {measurement.distractors_with_hits} dystraktorów, dozwolone "
        f"{MAX_DISTRACTORS_WITH_HITS} — próg przepuszcza zgłoszenia bez związku z zapytaniem"
    )
