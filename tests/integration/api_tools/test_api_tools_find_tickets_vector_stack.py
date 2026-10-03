"""
Description:
Test integracyjny narzędzia `find_tickets_vector` z prawdziwym embedderem i prawdziwym Qdrantem: czy
to, co zapisuje indeksacja, wraca przez narzędzie. Wymaga działającego stacku.

| scenariusz                                  | oczekiwanie                                 |
|---------------------------------------------|---------------------------------------------|
| pytanie polami zaindeksowanego zgłoszenia   | to zgłoszenie pierwsze i równe zapisanemu   |
| próg powyżej każdego możliwego podobieństwa | pusty wynik, komplet policzony jako odcięty |

Co się dzieje po drodze:

1. Fixture kasuje kolekcję testową i zapisuje trzy zmyślone zgłoszenia jako pliki JSON.
2. Indeksuje je produkcyjnym `TicketIndexer`: prawdziwy embedder liczy wektory, Qdrant je zapisuje.
3. Test pyta narzędzie polami `problem` i `symptoms` jednego ze zgłoszeń.
4. Po teście kolekcja jest kasowana, a połączenia zamykane.

O czym pamiętać przy zmianach:

- Kolekcja jest własna (`find_tickets_vector_integration_test`), nigdy skonfigurowana `tickets` —
  test ją tworzy i kasuje, a z prawdziwym indeksem skończyłoby się to jego utratą.
- Asercje są na ranking i równość rekordu, nigdy na wysokość score.
- Tryb embeddera, przestrzeń wektorów, liczenie progu i tłumaczenie błędów sprawdzają testy
  jednostkowe na podmienionym transporcie; trafność wyszukiwania to sprawa testów ewaluacyjnych.
"""

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path

import pytest

from app.config import Settings
from app.embedding import EmbeddingClient
from app.model.ticket_parsed import ParsedTicket
from app.retrieval import QdrantClient
from app.service.rag_indexer import TicketIndexer
from app.tools.find_tickets_vector import FindTicketsVectorQuery, FindTicketsVectorTool

pytestmark = [
    pytest.mark.stack,
    pytest.mark.stack_qdrant,
    pytest.mark.stack_embedder,
]

# Własna kolekcja, nigdy skonfigurowana — patrz opis modułu.
TEST_COLLECTION = "find_tickets_vector_integration_test"


def _ticket(
    ticket_id: str,  # np. "90001"
    component: str,  # np. "e-Doręczenia"
    problem:   str,  # np. "Nie przychodzą przesyłki z e-Doręczeń"
    symptoms:  str,  # np. "Brak nowych przesyłek, choć nadawcy potwierdzają wysyłkę"
    solution:  str,  # np. "Zrestartowano kolejkę pobierania."
) -> ParsedTicket:
    """
    Description:
    Jedno zmyślone zgłoszenie do zaindeksowania; zgłoszenia różnią się tematem, żeby ranking był
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
    ticket = ParsedTicket(
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

    return ticket


TICKETS = [
    _ticket(
        "90001",
        "e-Doręczenia",
        "Nie przychodzą przesyłki z e-Doręczeń",
        "Brak nowych przesyłek w skrzynce, choć nadawcy potwierdzają wysyłkę",
        "Zrestartowano kolejkę pobierania; zaległe przesyłki pobrały się same.",
    ),
    _ticket(
        "90002",
        "główna aplikacja",
        "Skanowanie wielu stron nie zapisuje dokumentu",
        "Przy kilkudziesięciu kartkach skan nie dociera do systemu, jedna strona przechodzi",
        "Podniesiono limit rozmiaru przesyłanego pliku na serwerze aplikacji.",
    ),
    _ticket(
        "90003",
        "główna aplikacja",
        "Kopie zapasowe bazy przestały się wykonywać",
        "Od kilku dni w katalogu kopii nie pojawiają się nowe pliki",
        "Poprawiono wpis w harmonogramie zadań, kopie wykonują się ponownie.",
    ),
]


@pytest.fixture
async def clients(
    host_settings: Settings,
    tmp_path:      Path,
) -> AsyncIterator[tuple[EmbeddingClient, QdrantClient]]:
    """
    Description:
    Oddaje klientów działających usług z kolekcją testową zaindeksowaną produkcyjną ścieżką
    (`TicketIndexer`) — narzędzie ma znaleźć to, co naprawdę zapisuje indeksacja. Kolekcja jest
    kasowana przed testem i po nim: przerwany przebieg nie zostawi starego stanu następnemu.

    Example args:
        host_settings=Settings(embedding_base_url="http://localhost:8001", …)
        tmp_path=Path("/tmp/pytest-0")

    Example result:
        (EmbeddingClient(…), QdrantClient(collection="find_tickets_vector_integration_test"))
    """
    embedder = EmbeddingClient(
        base_url = host_settings.embedding_base_url,
        timeout  = host_settings.embedding_timeout_seconds,
    )
    qdrant = QdrantClient(
        base_url   = host_settings.qdrant_url,
        collection = TEST_COLLECTION,
        timeout    = host_settings.qdrant_timeout_seconds,
    )

    await qdrant.delete_collection()

    for ticket in TICKETS:
        artifact = tmp_path / f"{ticket.ticket_id}.json"
        artifact.write_text(ticket.model_dump_json(), encoding="utf-8")

    indexer = TicketIndexer(
        embedder    = embedder,
        qdrant      = qdrant,
        vector_size = host_settings.embedding_vector_size,
    )
    await indexer.build(tmp_path)

    yield embedder, qdrant

    await qdrant.delete_collection()
    await embedder.aclose()
    await qdrant.aclose()


@pytest.mark.parametrize("ticket", TICKETS, ids=lambda ticket: ticket.ticket_id)
async def test_a_ticket_asked_by_its_own_fields_comes_back_first_and_whole(
    clients: tuple[EmbeddingClient, QdrantClient],
    ticket:  ParsedTicket,
) -> None:
    """Zapytanie polami zaindeksowanego zgłoszenia → to zgłoszenie na pierwszym miejscu, równe
    zapisanemu: payload z Qdranta wraca do `ParsedTicket` bez strat. Asercja na ranking, nie na
    wysokość score."""
    embedder, qdrant = clients
    tool   = FindTicketsVectorTool(embedder=embedder, qdrant=qdrant, top_k=5, score_min=-1.0)
    query  = FindTicketsVectorQuery(problem=ticket.problem, symptoms=ticket.symptoms)
    result = await tool.search(query)

    assert result.items[0].ticket == ticket
    assert len(result.items) == len(TICKETS)
    assert result.dropped_below_threshold == 0


async def test_a_threshold_nothing_passes_counts_everything_as_dropped(
    clients: tuple[EmbeddingClient, QdrantClient],
) -> None:
    """Próg powyżej każdego możliwego podobieństwa → pusty wynik i komplet policzony jako odcięty:
    ostry próg nie może wyglądać jak pusty indeks."""
    embedder, qdrant = clients
    tool   = FindTicketsVectorTool(embedder=embedder, qdrant=qdrant, top_k=5, score_min=1.1)
    result = await tool.search(
        FindTicketsVectorQuery(problem=TICKETS[0].problem, symptoms=TICKETS[0].symptoms)
    )

    assert result.items == []
    assert result.dropped_below_threshold == len(TICKETS)
