"""
Description:
Golden set zgłoszeń w testach ewaluacyjnych: zapytania i dystraktory w kształcie narzędzia
`find_tickets_vector`, korpus odniesienia z etykietami przeglądu i pomiary na nich — wyszukiwania
po znaczeniu na stacku i filtra jakości na plikach.

| co                         | do czego                                                     |
|----------------------------|--------------------------------------------------------------|
| `golden_set()`             | cały plik golden setu: liczniki z metryczki i wpisy          |
| `golden_queries()`         | zapytania przy wpisach z wiedzą, w parze z id rekordu-celu   |
| `distractor_queries()`     | zapytania bez odpowiednika w indeksie                        |
| `measure_tickets_vector()` | pomiar `find_tickets_vector` na kolekcji golden setu         |
| `corpus()`                 | artefakty korpusu odniesienia                                |
| `not_useful_ids()`         | id rekordów oznaczonych w przeglądzie jako bez wiedzy        |
| `measure_filter()`         | odrzucenia filtra jakości wobec etykiet przeglądu            |
| `golden_text_set()`        | zestaw tekstowy: zapytania z celem i bez celu                |
| `golden_thread()`          | wątek zgłoszenia golden setu po anonimizacji                 |
| `contains_phrase()`        | czy fraza stoi w tekście tak, jak szuka jej podciąg w bazie  |
| `measure_tickets_text()`   | pomiar `find_tickets_text` na tabeli wątków golden setu      |

O czym pamiętać przy zmianach:

- `data/` nie ma w repo (PII), więc fixture pomiaru sprawdza obecność plików i bez nich pomija
  testy; funkcje stąd zakładają, że pliki są.
- Zapytanie stoi też przy kilku wpisach bez wiedzy, na wypadek powrotu etykiety. Pomiar
  wyszukiwania bierze zapytania tylko przy wpisach z wiedzą, bo cel bez wiedzy filtr wyrzuca
  z indeksu i nie miałby jak wrócić.
- `query_problem` i `query_symptoms` napisano z samego `query_raw`, bez wglądu w rekord-cel. Nie
  wolno ich poprawiać pod wynik: zastępują zapytanie agenta do czasu pomiaru na prawdziwym modelu
  (p. 23).
- Pomiary czytają własną kolekcję i tabelę golden setu (`GOLDEN_COLLECTION`, `GOLDEN_TABLE`),
  a nie indeksy instancji, bo te trzymają pełny korpus (2026-11-13, tabela od 2026-11-15).
  Buduje je raz komenda z `BUILD_HINT`, a nie test, bo indeks 200 kart liczy się na CPU ponad
  dwie i pół minuty.
- Pomiar tekstowy sprawdza najpierw, czy tabela trzyma dokładnie wątki kart przyjętych przez
  filtr: tabela z innego korpusu dałaby liczby, które nic nie znaczą.
"""

import json

import pytest

from app.agent_tools.tickets.find_tickets_text import (
    FindTicketsTextQuery,
    FindTicketsTextTool,
)
from app.agent_tools.tickets.find_tickets_vector import (
    FindTicketsVectorQuery,
    FindTicketsVectorTool,
)
from app.config import Settings
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.filter_ticket_quality import filter_tickets
from app.db_postgres import DbPostgresMissingTableError, PostgresClient, TicketsTable
from app.db_qdrant import DbQdrantMissingCollectionError, QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests._helpers.golden_tickets.constants import (
    BUILD_HINT,
    CORPUS_DIR,
    DISTRACTORS_FILE,
    GOLDEN_COLLECTION,
    GOLDEN_FILE,
    GOLDEN_TABLE,
    TEXT_FILE,
    THREADS_DIR,
    WHITESPACE,
)
from tests._helpers.golden_tickets.models.filter_measurement import FilterMeasurement
from tests._helpers.golden_tickets.models.golden_query import GoldenQuery
from tests._helpers.golden_tickets.models.golden_set import GoldenSet
from tests._helpers.golden_tickets.models.golden_text_query import GoldenTextQuery
from tests._helpers.golden_tickets.models.golden_text_set import GoldenTextSet
from tests._helpers.golden_tickets.models.golden_ticket import GoldenTicket
from tests._helpers.golden_tickets.models.tickets_text_measurement import (
    TicketsTextMeasurement,
)
from tests._helpers.golden_tickets.models.tickets_vector_measurement import (
    TicketsVectorMeasurement,
)


def golden_set() -> GoldenSet:
    """
    Description:
    Czyta golden set zgłoszeń: liczniki z metryczki i wpisy w kolejności z pliku, każdy
    z etykietą przeglądu i zapytaniem, jeśli je ma.

    Example args:
        (brak)

    Example result:
        GoldenSet(counts={"useful": 135, "not_useful": 65, "queries": 126},
                  tickets=[GoldenTicket(ticket_id="5641", useful=True, …), …])
    """
    data    = json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))
    tickets = [
        GoldenTicket(
            ticket_id     = entry["ticket_id"],
            useful        = entry["useful"],
            useful_reason = entry["useful_reason"],
            query         = GoldenQuery(**entry["query"]) if "query" in entry else None,
        )
        for entry in data["tickets"]
    ]
    golden = GoldenSet(counts=data["meta"]["counts"], tickets=tickets)

    return golden


def golden_queries() -> list[tuple[str, FindTicketsVectorQuery]]:
    """
    Description:
    Czyta zapytania przy wpisach z wiedzą, w kształcie narzędzia, każde w parze z id
    rekordu-celu.

    Example args:
        (brak)

    Example result:
        [("90001", FindTicketsVectorQuery(problem="Nie przychodzą przesyłki…", symptoms="…")), …]
    """
    queries = [
        (
            ticket.ticket_id,
            FindTicketsVectorQuery(
                problem  = ticket.query.query_problem,
                symptoms = ticket.query.query_symptoms,
            ),
        )
        for ticket in golden_set().tickets
        if ticket.useful and ticket.query is not None
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
    w produkcie, z `RAG_TOP_K` i `RAG_SCORE_MIN` z konfiguracji, na kolekcji golden setu.
    Brakującą albo pustą kolekcję odrzuca od razu, z poleceniem, które ją buduje — inaczej
    wszystkie liczby wyszłyby zerowe i wyglądały na zepsute wyszukiwanie.

    Example args:
        settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        TicketsVectorMeasurement(target_first=119, target_returned=126, distractors_with_hits=7)

    Raises:
        Failed: kolekcji golden setu nie ma albo jest pusta
        EmbeddingError: embedder jest nieosiągalny albo odpowiedział błędem
        DbQdrantError: Qdrant jest nieosiągalny
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
        name        = GOLDEN_COLLECTION,
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
        try:
            indexed = await tickets.count()
        except DbQdrantMissingCollectionError:
            pytest.fail(f"nie ma kolekcji `{GOLDEN_COLLECTION}` — {BUILD_HINT}")

        if not indexed:
            pytest.fail(f"kolekcja `{GOLDEN_COLLECTION}` jest pusta — {BUILD_HINT}")

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


def not_useful_ids() -> set[str]:
    """
    Description:
    Czyta id zgłoszeń, które przegląd oznaczył jako niosące zero wiedzy (`useful` = false).

    Example args:
        (brak)

    Example result:
        {"8765", "27348", …}
    """
    return {ticket.ticket_id for ticket in golden_set().tickets if not ticket.useful}


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
    not_useful = not_useful_ids()
    report     = filter_tickets(corpus())
    dropped    = {verdict.ticket_id for verdict in report.dropped}

    measurement = FilterMeasurement(
        labelled_drops  = len(dropped & not_useful),
        false_positives = len(dropped - not_useful),
    )

    return measurement


def golden_text_set() -> GoldenTextSet:
    """
    Description:
    Czyta zestaw tekstowy: liczniki z metryczki, zapytania z celem i zapytania bez celu,
    w kolejności z pliku.

    Example args:
        (brak)

    Example result:
        GoldenTextSet(counts={"queries": 21, "distractors": 5},
                      queries=[GoldenTextQuery(ticket_id="5641", kind="komunikat_log", …), …],
                      distractors=[GoldenTextQuery(ticket_id=None, kind="komunikat_log", …), …])
    """
    data    = json.loads(TEXT_FILE.read_text(encoding="utf-8"))
    queries = [
        GoldenTextQuery(
            ticket_id  = entry["ticket_id"],
            kind       = entry["kind"],
            difficulty = entry["difficulty"],
            exact      = entry["exact"],
            words      = entry["words"],
            note       = entry.get("note"),
        )
        for entry in data["queries"]
    ]
    distractors = [
        GoldenTextQuery(
            ticket_id  = None,
            kind       = entry["kind"],
            difficulty = "typowe",
            exact      = entry["exact"],
            words      = entry.get("words"),
            note       = None,
        )
        for entry in data["distractors"]
    ]
    text_set = GoldenTextSet(
        counts      = data["meta"]["counts"],
        queries     = queries,
        distractors = distractors,
    )

    return text_set


def golden_thread(
    ticket_id: str,  # np. "18387"
) -> str:
    """
    Description:
    Czyta wątek zgłoszenia golden setu po anonimizacji, ten, z którego `reindex` buduje tabelę
    wątków golden setu.

    Example args:
        ticket_id="18387"

    Example result:
        "ZGŁOSZENIE 18387 z 2024-10-31\nTemat: …"
    """
    return (THREADS_DIR / f"{ticket_id}.txt").read_text(encoding="utf-8")


def contains_phrase(
    text:   str,  # np. "…pojawia się komunikat „Wygasły dane\nlogowania użytkownika”…"
    phrase: str,  # np. "wygasły dane logowania użytkownika"
) -> bool:
    """
    Description:
    Mówi, czy fraza stoi w tekście tak, jak szuka jej podciąg w bazie: bez względu na wielkość
    liter i na to, jak tekst złamano między liniami. Polskie litery muszą się zgadzać, jak w bazie.

    Example args:
        text="…komunikat „Wygasły dane\nlogowania użytkownika”…"
        phrase="wygasły dane logowania użytkownika"

    Example result:
        True
    """
    flat_text   = WHITESPACE.sub(" ", text).lower()
    flat_phrase = WHITESPACE.sub(" ", phrase).strip().lower()

    return flat_phrase in flat_text


async def measure_tickets_text(
    client: PostgresClient,  # np. build_postgres_client() — Postgres dostępny z hosta
    limit:  int,             # np. 5 — RAG_TOP_K
) -> TicketsTextMeasurement:
    """
    Description:
    Przepuszcza zestaw tekstowy przez `FindTicketsTextTool` zbudowane tak jak w produkcie,
    z limitem `RAG_TOP_K`, na tabeli wątków golden setu. Najpierw sprawdza, czy tabela trzyma
    dokładnie wątki kart przyjętych przez filtr jakości: brakująca, pusta albo zbudowana z innego
    korpusu tabela kończy test błędem z poleceniem, które ją buduje.

    Example args:
        client=build_postgres_client()
        limit=5

    Example result:
        TicketsTextMeasurement(target_first=19, target_returned=20, distractors_with_hits=0)

    Raises:
        Failed: tabeli wątków golden setu nie ma, jest pusta albo nie odpowiada korpusowi
        DbPostgresError: Postgres jest nieosiągalny
    """
    table = TicketsTable(client, GOLDEN_TABLE)
    tool  = FindTicketsTextTool(tickets=table, limit=limit)

    try:
        # --- warunek wstępny: tabela to dokładnie wątki kart przyjętych przez filtr ---
        try:
            indexed = await table.count()
        except DbPostgresMissingTableError:
            pytest.fail(f"nie ma tabeli `{GOLDEN_TABLE}` — {BUILD_HINT}")

        kept  = sorted(verdict.ticket_id for verdict in filter_tickets(corpus()).kept)
        found = {row.ticket_id for row in await table.read_by_id(kept)}

        if indexed != len(kept) or found != set(kept):
            pytest.fail(
                f"tabela `{GOLDEN_TABLE}` ma {indexed} wierszy, z tego {len(found)} z {len(kept)} "
                f"wątków kart przyjętych przez filtr — {BUILD_HINT}"
            )

        # --- zapytania z celem ---
        target_first    = 0
        target_returned = 0

        for query in golden_text_set().queries:
            result = await tool.find(FindTicketsTextQuery(exact=query.exact, words=query.words))
            ids    = [ticket.ticket_id for ticket in result.tickets]

            target_first    += ids[:1] == [query.ticket_id]
            target_returned += query.ticket_id in ids

        # --- zapytania bez celu: każde trafienie jest tu pomyłką ---
        distractors_with_hits = 0

        for query in golden_text_set().distractors:
            result = await tool.find(FindTicketsTextQuery(exact=query.exact, words=query.words))

            distractors_with_hits += bool(result.tickets)
    finally:
        await tool.aclose()

    measurement = TicketsTextMeasurement(
        target_first          = target_first,
        target_returned       = target_returned,
        distractors_with_hits = distractors_with_hits,
    )

    return measurement
