"""
Description:
Wspólne indeksy testów narzędzi agenta na stacku. Każde narzędzie ma w tym folderze własny plik
testów, a indeks, na którym stoi, buduje fixture stąd — raz napisany, bo te same zmyślone sekcje
i zgłoszenia czyta kilka narzędzi.

| fixture           | co buduje                              | kto używa                         |
|-------------------|----------------------------------------|-----------------------------------|
| `docs_index`      | trzy sekcje, przez `DocsIndexer`       | cztery narzędzia dokumentacji     |
| `tickets_cards`   | trzy karty, przez `TicketsIndexer`     | wyszukiwanie po znaczeniu i karty |
| `tickets_threads` | pięć wątków, wprost do tabeli zgłoszeń | wyszukiwanie tekstowe i wątki     |

Co się dzieje po drodze, w każdym fixture:

1. Kasuje własną tabelę albo kolekcję testu, na wypadek przerwanego poprzedniego przebiegu.
2. Buduje indeks ze zmyślonych danych — tam, gdzie indeksacja istnieje, produkcyjną ścieżką,
   żeby narzędzia czytały to, co naprawdę zapisuje indeksacja.
3. Oddaje testowi narzędzia RAZEM z danymi, z których powstał indeks: test porównuje wynik
   z tym, co zapisano, i nie importuje niczego z tego pliku.
4. Po teście kasuje indeks i zamyka połączenia.

O czym pamiętać przy zmianach:

- Tabele i kolekcje są własne (`*_stack_test`), nigdy skonfigurowane — fixture je kasuje,
  a z prawdziwym indeksem skończyłoby się to jego utratą.
- Dane są zmyślone. Wątki zgłoszeń to zestaw atrap, już „po anonimizacji": surowego wątku nie
  wolno wpisać do bazy nawet na próbę.
- Wątki idą do tabeli wprost, bo ich indeksacji jeszcze nie ma (p. 31).
- Markerów fixture nie niesie: czego test potrzebuje, deklaruje jego plik w `pytestmark`.
- Próg podobieństwa w narzędziach wyszukiwania po znaczeniu jest wyłączony: na trzech rekordach
  sprawdza się kolejność, nie odcinanie.
"""

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest

from app.agent_tools.docs.find_docs_text import FindDocsTextTool
from app.agent_tools.docs.find_docs_vector import FindDocsVectorTool
from app.agent_tools.docs.list_docs import ListDocsTool
from app.agent_tools.docs.read_docs import ReadDocsTool
from app.agent_tools.tickets.fake_tickets import default_threads
from app.agent_tools.tickets.find_tickets_text import FindTicketsTextTool
from app.agent_tools.tickets.find_tickets_vector import FindTicketsVectorTool
from app.agent_tools.tickets.read_tickets_card import ReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_thread import ReadTicketsThreadTool
from app.config import Settings
from app.core_model.docs.doc_directory import DocDirectory
from app.core_model.docs.doc_manifest import DocManifest
from app.core_model.docs.doc_manifest_section import DocManifestSection
from app.core_model.docs.doc_package import DocPackage
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.indexer_docs import DocsIndexer
from app.core_service.indexer_tickets import TicketsIndexer
from app.db_postgres import DocsTable, TicketRow, TicketsTable
from app.db_qdrant import DocsCollection, QdrantClient, TicketsCollection
from app.engine_embedding import EmbeddingClient
from tests.conftest import build_postgres_client

# Własne indeksy, nigdy skonfigurowane — patrz opis modułu.
DOCS_TABLE         = "docs_text_tools_stack_test"
DOCS_COLLECTION    = "docs_tools_stack_test"
TICKETS_COLLECTION = "tickets_tools_stack_test"
TICKETS_TABLE      = "tickets_text_tools_stack_test"

# Mały limit, żeby trzy akapity sekcji `adm-zwierzeta` dały trzy fragmenty.
FRAGMENT_CHARS = 80

# Treści o trzech niezwiązanych tematach: asercja na ranking nie może zależeć od niuansu.
# W sekcji o ekspresie komunikat jest złamany między liniami, jak w pliku zawiniętym na szerokość.
# Kolejność jest kolejnością metryczki i celowo nie jest alfabetyczna: po niej stoi spis treści.
DOC_BODIES = {
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


class DocsIndex(NamedTuple):
    """
    Description:
    Cztery narzędzia dokumentacji na indeksie testu i treści, z których go zbudowano.
    """

    vector:  FindDocsVectorTool
    text:    FindDocsTextTool
    listing: ListDocsTool
    read:    ReadDocsTool
    # Treść każdej sekcji po identyfikatorze, w kolejności metryczki.
    bodies:  dict[str, str]


class TicketsCards(NamedTuple):
    """
    Description:
    Narzędzia zgłoszeń stojące na Qdrancie, na kolekcji testu, i karty, z których ją zbudowano.
    Embedder i kolekcja są obok, dla testu, który buduje wyszukiwanie z własnym progiem.
    """

    find:       FindTicketsVectorTool
    read:       ReadTicketsCardTool
    embedder:   EmbeddingClient
    collection: TicketsCollection
    cards:      list[ParsedTicket]


class TicketsThreads(NamedTuple):
    """
    Description:
    Narzędzia zgłoszeń stojące na Postgresie, na tabeli testu, i wiersze, które do niej zapisano.
    """

    find: FindTicketsTextTool
    read: ReadTicketsThreadTool
    rows: list[TicketRow]


def _doc_package() -> DocPackage:
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
            for section_id in DOC_BODIES
        ],
    )
    directory = DocDirectory(path=Path("pamiec/biuro"), manifest=manifest, bodies=DOC_BODIES)
    package   = DocPackage(path=Path("pamiec"), directories=[directory])

    return package


def _card(
    ticket_id: str,  # np. "90001"
    component: str,  # np. "e-Doręczenia"
    problem:   str,  # np. "Nie przychodzą przesyłki z e-Doręczeń"
    symptoms:  str,  # np. "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę"
    solution:  str,  # np. "Zrestartowano kolejkę pobierania."
) -> ParsedTicket:
    """
    Description:
    Jedna zmyślona karta do zaindeksowania; karty różnią się tematem, żeby ranking był
    jednoznaczny.

    Example args:
        ticket_id="90001"
        component="e-Doręczenia"
        problem="Nie przychodzą przesyłki z e-Doręczeń"
        symptoms="Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę"
        solution="Zrestartowano kolejkę pobierania."

    Example result:
        ParsedTicket(ticket_id="90001", component="e-Doręczenia", …)
    """
    card = ParsedTicket(
        ticket_id                     = ticket_id,
        date                          = date(2026, 2, 10),
        component                     = component,
        problem                       = problem,
        symptoms                      = symptoms,
        error_codes                   = ["ERR-4210"],
        cause                         = "brak",
        solution                      = solution,
        resolution                    = "naprawione",
        resolution_vocabulary_version = 1,
        questions_summary             = "pytano, od kiedy występuje problem",
    )

    return card


CARDS = [
    _card(
        "90001",
        "e-Doręczenia",
        "Nie przychodzą przesyłki z e-Doręczeń",
        "Brak nowych przesyłek w skrzynce, choć nadawcy potwierdzają wysyłkę",
        "Zrestartowano kolejkę pobierania; zaległe przesyłki pobrały się same.",
    ),
    _card(
        "90002",
        "główna aplikacja",
        "Skanowanie wielu stron nie zapisuje dokumentu",
        "Przy kilkudziesięciu kartkach skan nie dociera do systemu, jedna strona przechodzi",
        "Podniesiono limit rozmiaru przesyłanego pliku na serwerze aplikacji.",
    ),
    _card(
        "90003",
        "główna aplikacja",
        "Kopie zapasowe bazy przestały się wykonywać",
        "Od kilku dni w katalogu kopii nie pojawiają się nowe pliki",
        "Poprawiono wpis w harmonogramie zadań, kopie wykonują się ponownie.",
    ),
]


@pytest.fixture
async def docs_index(
    host_settings: Settings,
) -> AsyncIterator[DocsIndex]:
    """
    Description:
    Oddaje cztery narzędzia dokumentacji na własnej tabeli i kolekcji testu, zaindeksowanych
    produkcyjną ścieżką (`DocsIndexer`): prawdziwy embedder liczy wektory fragmentów, Qdrant
    i Postgres je zapisują.

    Example args:
        host_settings=Settings(embedding_base_url="http://localhost:8001", …)

    Example result:
        DocsIndex(vector=FindDocsVectorTool(…), text=FindDocsTextTool(…),
                  listing=ListDocsTool(…), read=ReadDocsTool(…), bodies={"adm-zwierzeta": "…", …})
    """
    embedder = EmbeddingClient(
        base_url = host_settings.embedding_base_url,
        timeout  = host_settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = host_settings.qdrant_url,
        timeout  = host_settings.qdrant_timeout_seconds,
    )
    table      = DocsTable(build_postgres_client(), name=DOCS_TABLE)
    collection = DocsCollection(qdrant, DOCS_COLLECTION, host_settings.embedding_vector_size)
    indexer = DocsIndexer(
        embedder       = embedder,
        table          = table,
        collection     = collection,
        fragment_chars = FRAGMENT_CHARS,
        synthetic      = True,
    )

    await indexer.rebuild(_doc_package())

    yield DocsIndex(
        vector  = FindDocsVectorTool(embedder=embedder, docs=collection, top_k=5, score_min=-1.0),
        text    = FindDocsTextTool(docs=table, limit=5),
        listing = ListDocsTool(docs=table),
        read    = ReadDocsTool(docs=table),
        bodies  = DOC_BODIES,
    )

    await table.drop()
    await collection.drop()
    await indexer.aclose()


@pytest.fixture
async def tickets_cards(
    host_settings: Settings,
    tmp_path:      Path,
) -> AsyncIterator[TicketsCards]:
    """
    Description:
    Oddaje wyszukiwanie po znaczeniu i odczyt kart na własnej kolekcji testu, zaindeksowanej
    produkcyjną ścieżką (`TicketsIndexer`) z trzech zmyślonych kart zapisanych jako pliki JSON.

    Example args:
        host_settings=Settings(embedding_base_url="http://localhost:8001", …)
        tmp_path=Path("/tmp/pytest-0")

    Example result:
        TicketsCards(find=FindTicketsVectorTool(…), read=ReadTicketsCardTool(…),
                     embedder=EmbeddingClient(…), collection=TicketsCollection(…), cards=[…])
    """
    embedder = EmbeddingClient(
        base_url = host_settings.embedding_base_url,
        timeout  = host_settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url = host_settings.qdrant_url,
        timeout  = host_settings.qdrant_timeout_seconds,
    )
    collection = TicketsCollection(
        client      = qdrant,
        name        = TICKETS_COLLECTION,
        vector_size = host_settings.embedding_vector_size,
    )

    await collection.drop()

    for card in CARDS:
        artifact = tmp_path / f"{card.ticket_id}.json"
        artifact.write_text(card.model_dump_json(), encoding="utf-8")

    indexer = TicketsIndexer(embedder=embedder, tickets=collection)
    await indexer.build(tmp_path)

    yield TicketsCards(
        find = FindTicketsVectorTool(
            embedder  = embedder,
            tickets   = collection,
            top_k     = 5,
            score_min = -1.0,
        ),
        read       = ReadTicketsCardTool(tickets=collection),
        embedder   = embedder,
        collection = collection,
        cards      = CARDS,
    )

    await collection.drop()
    await embedder.aclose()
    await qdrant.aclose()


@pytest.fixture
async def tickets_threads() -> AsyncIterator[TicketsThreads]:
    """
    Description:
    Oddaje wyszukiwanie tekstowe i odczyt wątków na własnej tabeli testu z pięcioma zmyślonymi
    wątkami z zestawu atrap.

    Example args:
        (brak)

    Example result:
        TicketsThreads(find=FindTicketsTextTool(…), read=ReadTicketsThreadTool(…), rows=[…])
    """
    rows  = default_threads()
    table = TicketsTable(build_postgres_client(), name=TICKETS_TABLE)

    await table.drop()
    await table.create()
    await table.upsert(rows)

    yield TicketsThreads(
        find = FindTicketsTextTool(tickets=table, limit=5),
        read = ReadTicketsThreadTool(tickets=table),
        rows = rows,
    )

    await table.drop()
    await table.aclose()
