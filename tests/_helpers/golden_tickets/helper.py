"""
Description:
Golden set zgłoszeń w testach ewaluacyjnych: zapytania i dystraktory w kształcie narzędzia
`find_tickets_vector`, korpus odniesienia z etykietami przeglądu i pomiary na nich — wyszukiwania
po znaczeniu na stacku i filtra jakości na plikach.

| co                         | do czego                                                     |
|----------------------------|--------------------------------------------------------------|
| `golden_queries()`         | zapytania golden setu w parze z id rekordu-celu              |
| `distractor_queries()`     | zapytania bez odpowiednika w indeksie                        |
| `measure_tickets_vector()` | pomiar `find_tickets_vector` na skonfigurowanej kolekcji     |
| `corpus()`                 | artefakty korpusu odniesienia                                |
| `rejected_ids()`           | id rekordów oznaczonych w przeglądzie jako bez wiedzy        |
| `measure_filter()`         | odrzucenia filtra jakości wobec etykiet przeglądu            |

O czym pamiętać przy zmianach:

- `data/` nie ma w repo (PII), więc fixture pomiaru sprawdza obecność plików i bez nich pomija
  testy; funkcje stąd zakładają, że pliki są.
- `query_problem` i `query_symptoms` napisano z samego `query_raw`, bez wglądu w rekord-cel. Nie
  wolno ich poprawiać pod wynik: zastępują zapytanie agenta do czasu pomiaru na prawdziwym modelu
  (p. 23).
- Kolekcją jest skonfigurowana kolekcja, a nie własna, bo zbudowanie własnej z 200 artefaktów
  trwa na CPU ponad dwie i pół minuty.
"""

import json

from app.agent_tools.tickets.find_tickets_vector import (
    FindTicketsVectorQuery,
    FindTicketsVectorTool,
)
from app.config import Settings
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.filter_ticket_quality import filter_tickets
from app.db_qdrant import QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests._helpers.golden_tickets.constants import (
    BUILD_HINT,
    CORPUS_DIR,
    DISTRACTORS_FILE,
    GOLDEN_FILE,
)
from tests._helpers.golden_tickets.models.filter_measurement import FilterMeasurement
from tests._helpers.golden_tickets.models.tickets_vector_measurement import (
    TicketsVectorMeasurement,
)


def golden_queries() -> list[tuple[str, FindTicketsVectorQuery]]:
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


def distractor_queries() -> list[FindTicketsVectorQuery]:
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


async def measure_tickets_vector(
    settings: Settings,  # np. Settings(embedding_base_url="http://localhost:8001", …)
) -> TicketsVectorMeasurement:
    """
    Description:
    Przepuszcza golden set i dystraktory przez `FindTicketsVectorTool` zbudowane tak jak
    w produkcie: skonfigurowana kolekcja, `RAG_TOP_K` i `RAG_SCORE_MIN` z konfiguracji. Pustą
    kolekcję odrzuca od razu — inaczej wszystkie liczby wyszłyby zerowe i wyglądały na zepsute
    wyszukiwanie.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        TicketsVectorMeasurement(target_first=119, target_returned=126, distractors_with_hits=7)

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

        assert indexed > 0, f"kolekcja `{settings.qdrant_collection}` jest pusta — {BUILD_HINT}"

        # --- zapytania z rekordem-celem ---
        target_first    = 0
        target_returned = 0

        for target, query in golden_queries():
            result = await tool.find(query)
            found  = [item.ticket_id for item in result.tickets]

            target_first    += found[:1] == [target]
            target_returned += target in found

        # --- dystraktory: każde trafienie jest tu pomyłką ---
        distractors_with_hits = 0

        for query in distractor_queries():
            result = await tool.find(query)

            distractors_with_hits += bool(result.tickets)
    finally:
        await tool.aclose()

    measurement = TicketsVectorMeasurement(
        target_first          = target_first,
        target_returned       = target_returned,
        distractors_with_hits = distractors_with_hits,
    )

    return measurement


def corpus() -> list[ParsedTicket]:
    """
    Description:
    Czyta wszystkie artefakty korpusu odniesienia, w kolejności posortowanej.

    Example args:
        (brak)

    Example result:
        [ParsedTicket(ticket_id="10012", …), …]
    """
    tickets = [
        ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_DIR.glob("*.json"))
    ]

    return tickets


def rejected_ids() -> set[str]:
    """
    Description:
    Czyta id zgłoszeń, które przegląd oznaczył jako niosące zero wiedzy.

    Example args:
        (brak)

    Example result:
        {"19596", "27348", …}
    """
    labels = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))

    return {str(entry["ticket_id"]) for entry in labels["rejected"]}


def measure_filter() -> FilterMeasurement:
    """
    Description:
    Przepuszcza filtr jakości przez korpus odniesienia i liczy, ile odrzuceń trafiło w rekordy
    oznaczone w przeglądzie jako bez wiedzy, a ile w rekordy uznane za dobre.

    Example args:
        (brak)

    Example result:
        FilterMeasurement(labelled_drops=59, false_positives=0)
    """
    rejected = rejected_ids()
    report   = filter_tickets(corpus())
    dropped  = {verdict.ticket_id for verdict in report.dropped}

    measurement = FilterMeasurement(
        labelled_drops  = len(dropped & rejected),
        false_positives = len(dropped - rejected),
    )

    return measurement
