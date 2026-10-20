"""
Description:
Serwis liczący indeksy (`IndexInspector`) na prawdziwych kolekcjach i tabelach, pod którymi
podmienieni są tylko klienci: Qdrant odpowiada z atrapy transportu, Postgres to
`ScriptedPostgres`. Do testów serwisu i trasy `GET /instance`.

| funkcja                | co oddaje                                                          |
|------------------------|--------------------------------------------------------------------|
| `counting_qdrant()`    | klient Qdranta, który liczy punkty dwóch kolekcji albo ich nie ma  |
| `failing_qdrant()`     | klient Qdranta, który na każde żądanie odpowiada błędem 500        |
| `counting_postgres()`  | klient Postgresa, który liczy wiersze tabeli albo jej nie ma       |
| `failing_postgres()`   | klient Postgresa, który na liczenie odpowiada awarią bazy          |
| `inspector_on()`       | serwis na podanych klientach i opisie paczki kodu                  |
| `scripted_inspector()` | serwis z liczbami podanymi wprost, na paczce syntetycznej          |
| `app_with_inspector()` | aplikacja `api`, której trasa `GET /instance` dostaje podany serwis |

Przykład — karty są, tabela wątków pusta, dokumentacji nie ma:

    inspector = scripted_inspector(cards=171, threads=0, sections=None, fragments=None)
    report    = await inspector.inspect()

    [status.state for status in report.indexes]
    # ["built", "empty", "missing", "missing", "built"]

O czym pamiętać przy zmianach:

- `None` w liczbie znaczy „indeksu nie ma": Qdrant odpowiada wtedy 404, a tabela błędem
  brakującej tabeli — tak, jak robią to prawdziwe bazy (sprawdzają to testy na stacku).
- Paczka kodu to domyślnie paczka syntetyczna z repo, zbudowana skryptem przed testami.
"""

import httpx
from fastapi import FastAPI

from app.core_service.factory_index_inspector import get_index_inspector
from app.core_service.inspector_indexes import IndexInspector
from app.core_service.loader_code_description import CodeDescription
from app.db_postgres import DbPostgresError, DbPostgresMissingTableError, DocsTable, TicketsTable
from app.db_qdrant import DocsCollection, QdrantClient, TicketsCollection
from app.main import create_app
from tests._helpers.instance.constants import (
    DOCS_COLLECTION,
    QDRANT_URL,
    TICKETS_COLLECTION,
    VECTOR_SIZE,
)
from tests._helpers.postgres import ScriptedPostgres
from tests._helpers.synthetic_code import synthetic_code_description
from tests._helpers.transport import always, routed, with_transport


def counting_qdrant(
    cards:     int | None,  # np. 171; None — kolekcji kart nie ma
    fragments: int | None,  # np. None — kolekcji dokumentacji nie ma
) -> QdrantClient:
    """
    Description:
    Klient Qdranta na atrapie transportu, który na liczenie punktów kolekcji kart i kolekcji
    dokumentacji oddaje podane liczby, a dla kolekcji bez liczby odpowiada 404 — jak Qdrant,
    gdy kolekcji nie ma.

    Example args:
        cards=171
        fragments=None

    Example result:
        QdrantClient: 171 punktów w „tickets", 404 dla „docs"
    """
    routes = {}

    for name, count in ((TICKETS_COLLECTION, cards), (DOCS_COLLECTION, fragments)):
        answer = (
            httpx.Response(404, json={"status": {"error": f"Collection `{name}` doesn't exist!"}})
            if count is None
            else httpx.Response(200, json={"result": {"count": count}, "status": "ok"})
        )
        routes[("POST", f"/collections/{name}/points/count")] = answer

    client = with_transport(QdrantClient(base_url=QDRANT_URL, timeout=1.0), routed(routes))

    return client


def failing_qdrant() -> QdrantClient:
    """
    Description:
    Klient Qdranta na atrapie transportu, który na każde żądanie odpowiada błędem 500 — Qdrant
    działa, ale zawodzi. To nie jest brak kolekcji.

    Example args:
        (brak)

    Example result:
        QdrantClient odpowiadający 500 na liczenie każdej kolekcji
    """
    return with_transport(QdrantClient(base_url=QDRANT_URL, timeout=1.0), always(status=500))


def counting_postgres(
    count: int | None,  # np. 0; None — tabeli nie ma
) -> ScriptedPostgres:
    """
    Description:
    Klient Postgresa bez bazy, który na liczenie wierszy tabeli oddaje podaną liczbę, a bez
    liczby zgłasza błąd brakującej tabeli — jak prawdziwy klient, gdy tabeli nie ma.

    Example args:
        count=None

    Example result:
        ScriptedPostgres zgłaszający DbPostgresMissingTableError przy liczeniu
    """
    missing = DbPostgresMissingTableError("w bazie 'helpdesk' nie ma tabeli z zapytania")
    rows    = [{"id": str(number)} for number in range(count or 0)]

    client = ScriptedPostgres(key="id", rows=rows, count_error=missing if count is None else None)

    return client


def failing_postgres() -> ScriptedPostgres:
    """
    Description:
    Klient Postgresa bez bazy, który na liczenie wierszy zgłasza awarię bazy — baza nie
    odpowiada. To nie jest brak tabeli.

    Example args:
        (brak)

    Example result:
        ScriptedPostgres zgłaszający DbPostgresError przy liczeniu
    """
    failure = DbPostgresError("zapytanie do Postgresa nie powiodło się: connection refused")

    return ScriptedPostgres(key="id", count_error=failure)


def inspector_on(
    qdrant:   QdrantClient,      # np. counting_qdrant(cards=171, fragments=None)
    threads:  ScriptedPostgres,  # np. counting_postgres(0)
    sections: ScriptedPostgres,  # np. counting_postgres(None)
    code:     CodeDescription,   # np. synthetic_code_description()
) -> IndexInspector:
    """
    Description:
    Serwis liczący indeksy na prawdziwych kolekcjach i tabelach, postawionych na podanych
    klientach, i na podanym opisie paczki kodu.

    Example args:
        qdrant=counting_qdrant(cards=171, fragments=None)
        threads=counting_postgres(0)
        sections=counting_postgres(None)
        code=synthetic_code_description()

    Example result:
        IndexInspector liczący kolekcje „tickets" i „docs", dwie tabele i paczkę syntetyczną
    """
    inspector = IndexInspector(
        tickets_cards   = TicketsCollection(qdrant, TICKETS_COLLECTION, VECTOR_SIZE),
        tickets_threads = TicketsTable(threads),
        docs_sections   = DocsTable(sections),
        docs_fragments  = DocsCollection(qdrant, DOCS_COLLECTION, VECTOR_SIZE),
        code            = code,
    )

    return inspector


def scripted_inspector(
    cards:     int | None = 171,                # punkty kolekcji kart; None — kolekcji nie ma
    threads:   int | None = 0,                  # wiersze tabeli wątków; None — tabeli nie ma
    sections:  int | None = None,               # wiersze tabeli dokumentacji
    fragments: int | None = None,               # punkty kolekcji dokumentacji
    code:      CodeDescription | None = None,   # None — paczka syntetyczna z repo
) -> IndexInspector:
    """
    Description:
    Serwis liczący indeksy z liczbami podanymi wprost. Domyślnie stan instancji pokazowej: karty
    są, tabela wątków pusta, dokumentacji nie ma, a paczka kodu to paczka syntetyczna.

    Example args:
        cards=171
        threads=0
        sections=None
        fragments=None
        code=None

    Example result:
        IndexInspector, którego raport ma stany built, empty, missing, missing, built
    """
    inspector = inspector_on(
        qdrant   = counting_qdrant(cards=cards, fragments=fragments),
        threads  = counting_postgres(threads),
        sections = counting_postgres(sections),
        code     = code or synthetic_code_description(),
    )

    return inspector


def app_with_inspector(
    inspector: IndexInspector,  # np. scripted_inspector()
) -> FastAPI:
    """
    Description:
    Aplikacja `api`, w której trasa `GET /instance` dostaje podany serwis zamiast serwisu
    z konfiguracji.

    Example args:
        inspector=scripted_inspector()

    Example result:
        FastAPI z podmienioną zależnością `get_index_inspector`
    """
    app = create_app()

    app.dependency_overrides[get_index_inspector] = lambda: inspector

    return app
