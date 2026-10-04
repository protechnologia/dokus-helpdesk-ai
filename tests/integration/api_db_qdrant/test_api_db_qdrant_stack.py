import math
from collections.abc import AsyncIterator

import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.doc_section import DocSection
from app.db_qdrant import (
    VECTOR_PROBLEM,
    VECTOR_STS,
    DbQdrantConfigError,
    DbQdrantError,
    DocPoint,
    DocsCollection,
    QdrantClient,
    TicketPoint,
    TicketsCollection,
    point_id_for,
)
from tests.conftest import qdrant_url

pytestmark = [pytest.mark.stack, pytest.mark.stack_qdrant]

# Co mieszka POZA naszym kodem i dlatego jest warte działającej usługi: że Qdrant naprawdę
# przyjmuje kolekcję z nazwanymi wektorami, trzyma payload obok wektorów, oddaje punkt pod
# identyfikatorem, który wyliczyliśmy, sortuje po podobieństwie i zgłasza rozjazd wymiaru, zamiast
# się dopasować. Kształt żądań, partie i tłumaczenie błędów sprawdzają testy jednostkowe.
#
# Niedostępny Qdrant wywala te testy, nigdy ich nie pomija (CLAUDE.md -> „Testy").

# Własne kolekcje, nigdy skonfigurowana: te testy zakładają i KASUJĄ to, czego dotykają.
TICKETS_NAME = "tickets_integration_test"
DOCS_NAME    = "docs_integration_test"

# Mały i celowo inny niż produkcyjne 768: nic tu nie zależy od prawdziwego wymiaru.
SIZE = 4

SECTIONS = default_sections()


def _ticket_point(
    ticket_id: str,          # np. "33644"
    fill:      float = 0.1,  # każda składowa wektora `problem`
) -> TicketPoint:
    """
    Description:
    Buduje punkt zgłoszenia z rozpoznawalnymi wektorami i zmyślonym payloadem. Ręcznie, nie
    z `ParsedTicket`: ten plik testuje przechowywanie, a zmiana schematu karty nie ma go psuć.

    Example args:
        ticket_id="33644"
        fill=0.1

    Example result:
        TicketPoint(point_id="df3b51f3-…", payload={"ticket_id": "33644", …})
    """
    point = TicketPoint(
        point_id       = point_id_for(ticket_id),
        vector_problem = [fill] * SIZE,
        # Przeciwny zwrot, żeby zamieniona para nazwanych wektorów była widoczna przy odczycie.
        vector_sts     = [-fill] * SIZE,
        payload        = {
            "ticket_id": ticket_id,
            "date":      "2026-03-14",
            "component": "ePUAP",
            "problem":   "Wysyłka przez ePUAP kończy się błędem komunikacji",
            "cause":     "Certyfikat bez uprawnienia AddDocumentToSign",
            "solution":  "Wygenerowano certyfikat z właściwym uprawnieniem.",
        },
    )

    return point


def _cosine(
    first:  list[float],  # np. [0.5, 0.5, 0.5, 0.5] — odczytany z Qdranta
    second: list[float],  # np. [0.1, 0.1, 0.1, 0.1] — zapisany
) -> float:
    """
    Description:
    Podobieństwo cosinusowe dwóch wektorów — do porównania wektora odczytanego z zapisanym po
    KIERUNKU. Kolekcja `Cosine` normalizuje wektory przy zapisie, więc równość padłaby przy
    poprawnie zapisanym wektorze.

    Example args:
        first=[0.5, 0.5, 0.5, 0.5]
        second=[0.1, 0.1, 0.1, 0.1]

    Example result:
        1.0
    """
    dot   = sum(a * b for a, b in zip(first, second, strict=True))
    norms = math.sqrt(sum(a * a for a in first)) * math.sqrt(sum(b * b for b in second))

    return dot / norms


@pytest.fixture
async def client() -> AsyncIterator[QdrantClient]:
    """
    Description:
    Oddaje klienta działającego Qdranta — jednego dla obu kolekcji — i zamyka go po teście.

    Example args:
        (brak)

    Example result:
        QdrantClient dla http://localhost:6333
    """
    client = QdrantClient(base_url=qdrant_url(), timeout=10.0)

    yield client

    await client.aclose()


@pytest.fixture
async def tickets(
    client: QdrantClient,
) -> AsyncIterator[TicketsCollection]:
    """
    Description:
    Oddaje kolekcję zgłoszeń o testowej nazwie, kasowaną przed testem i po nim. Przed też:
    test przerwany w połowie zostawiłby kolekcję, na której następny sprawdzałby stary stan.

    Example args:
        client=QdrantClient(base_url="http://localhost:6333")

    Example result:
        TicketsCollection „tickets_integration_test"
    """
    collection = TicketsCollection(client, TICKETS_NAME, SIZE)

    await collection.drop()

    yield collection

    await collection.drop()


@pytest.fixture
async def docs(
    client: QdrantClient,
) -> AsyncIterator[DocsCollection]:
    """
    Description:
    Oddaje kolekcję dokumentacji o testowej nazwie, kasowaną przed testem i po nim.

    Example args:
        client=QdrantClient(base_url="http://localhost:6333")

    Example result:
        DocsCollection „docs_integration_test"
    """
    collection = DocsCollection(client, DOCS_NAME, SIZE)

    await collection.drop()

    yield collection

    await collection.drop()


# --- zgłoszenia ---------------------------------------------------------------------------

async def test_tickets_are_created_with_both_named_vectors(tickets: TicketsCollection) -> None:
    """Świeża kolekcja → Qdrant naprawdę przyjmuje dwa nazwane wektory, a ponowne `ensure()`
    sprawdza PRAWDZIWY opis kolekcji i mówi „już była", zamiast ją przepisywać."""
    assert await tickets.ensure() is True
    assert await tickets.ensure() is False


async def test_a_ticket_reads_back_with_its_payload_and_both_vectors(
    tickets: TicketsCollection,
) -> None:
    """Zapisany punkt → odczytany po numerze zgłoszenia, z nietkniętym payloadem i każdym
    wektorem na swoim miejscu. Na tym stoi cała indeksacja."""
    await tickets.ensure()

    point = _ticket_point("33644")

    assert await tickets.upsert([point]) == 1

    stored = (await tickets.read_by_id(["33644"]))[0]

    assert stored.point_id == point.point_id
    assert stored.payload  == point.payload

    # Porównanie po KIERUNKU: [0.1]*4 wraca jako [0.5]*4, bo kolekcja `Cosine` normalizuje przy
    # zapisie. Nas to nie kosztuje nic, ale asercja na równość padłaby przy poprawnym systemie.
    assert _cosine(stored.vector_problem, point.vector_problem) == pytest.approx(1.0)
    # `sts` ma tu zwrot przeciwny, więc to także dowód, że nazwane wektory się nie zamieniły.
    assert _cosine(stored.vector_sts, point.vector_sts)         == pytest.approx(1.0)
    assert _cosine(stored.vector_problem, stored.vector_sts)    == pytest.approx(-1.0)


async def test_tickets_read_back_in_the_order_asked_and_without_the_missing(
    tickets: TicketsCollection,
) -> None:
    """Trzy numery, w tym jeden spoza kolekcji → dwa punkty w kolejności zapytania. Kolejność
    odpowiedzi nie jest obietnicą Qdranta, a brak punktu nie jest u niego błędem."""
    await tickets.ensure()
    await tickets.upsert([_ticket_point("33644"), _ticket_point("10718")])

    points = await tickets.read_by_id(["10718", "99999", "33644"])

    assert [point.ticket_id for point in points] == ["10718", "33644"]


async def test_reupserting_the_same_ticket_overwrites_it(tickets: TicketsCollection) -> None:
    """To samo zgłoszenie zapisane dwa razy → jeden punkt. Dzięki temu przebudowa nadpisuje
    korpus, zamiast go dublować."""
    await tickets.ensure()

    await tickets.upsert([_ticket_point("33644", fill=0.1)])
    await tickets.upsert([_ticket_point("33644", fill=0.9)])

    assert await tickets.count() == 1


async def test_a_wrong_vector_size_is_refused_against_a_real_collection(
    client:  QdrantClient,
    tickets: TicketsCollection,
) -> None:
    """Kolekcja w jednym wymiarze, konfiguracja mówi inny → błąd konfiguracji, sprawdzony wobec
    PRAWDZIWEGO opisu kolekcji, którego kształtu nie my ustalamy."""
    await tickets.ensure()

    with pytest.raises(DbQdrantConfigError):
        await TicketsCollection(client, TICKETS_NAME, SIZE + 1).ensure()


async def test_search_ranks_the_nearest_ticket_first(tickets: TicketsCollection) -> None:
    """Wektor zapytania → trafienia w kolejności prawdziwego podobieństwa, z payloadem.
    Sortuje Qdrant, nie my, więc tej połowy nie dowiedzie żaden test w procesie."""
    await tickets.ensure()

    # Dwa punkty o różnych kierunkach, żeby o „najbliższym" rozstrzygały dane, nie kolejność
    # zapisu.
    near = _ticket_point("33644", fill=0.1)
    far  = TicketPoint(
        point_id       = point_id_for("10718"),
        vector_problem = [0.1, 0.1, -0.1, -0.1],
        vector_sts     = [0.2] * SIZE,
        payload        = {"ticket_id": "10718"},
    )

    await tickets.upsert([near, far])

    hits = await tickets.search(vector=near.vector_problem, vector_name=VECTOR_PROBLEM, limit=5)

    assert [hit.ticket_id for hit in hits] == ["33644", "10718"]
    assert hits[0].payload["solution"]     == near.payload["solution"]
    assert hits[0].score > hits[1].score


async def test_search_reads_the_named_space_it_was_asked_for(tickets: TicketsCollection) -> None:
    """Ten sam wektor wobec `problem` i wobec `sts` → różne podobieństwa. To pomyłka, która się
    nie ogłasza: obie przestrzenie odpowiadają, a zła oddaje wiarygodne trafienia."""
    await tickets.ensure()

    point = _ticket_point("33644")

    await tickets.upsert([point])

    on_problem = await tickets.search(
        vector=point.vector_problem, vector_name=VECTOR_PROBLEM, limit=1
    )
    on_sts     = await tickets.search(
        vector=point.vector_problem, vector_name=VECTOR_STS, limit=1
    )

    assert on_problem[0].score == pytest.approx(1.0)
    # To samo zapytanie, ten sam punkt, druga przestrzeń — i nic nie zgłasza błędu. Dlatego
    # nazwa wektora jest argumentem wymaganym.
    assert on_sts[0].score     == pytest.approx(-1.0)


async def test_search_of_an_unknown_named_vector_is_an_error(tickets: TicketsCollection) -> None:
    """Literówka w nazwie wektora → `DbQdrantError` z PRAWDZIWEGO Qdranta, nigdy pusta lista."""
    await tickets.ensure()
    await tickets.upsert([_ticket_point("33644")])

    with pytest.raises(DbQdrantError):
        await tickets.search(vector=[0.1] * SIZE, vector_name="problme", limit=5)


async def test_reading_from_a_missing_collection_is_an_error(tickets: TicketsCollection) -> None:
    """Odczyt i licznik na kolekcji, której nie ma → `DbQdrantError`, nie pusty wynik: pusta
    lista wyglądałaby jak „nie ma takiego zgłoszenia"."""
    with pytest.raises(DbQdrantError):
        await tickets.read_by_id(["33644"])

    with pytest.raises(DbQdrantError):
        await tickets.count()


async def test_dropping_removes_the_collection(tickets: TicketsCollection) -> None:
    """Skasowana kolekcja → naprawdę jej nie ma, a ponowne kasowanie mówi „nie było czego"."""
    await tickets.ensure()

    assert await tickets.drop() is True
    assert await tickets.drop() is False


# --- dokumentacja -------------------------------------------------------------------------

async def test_docs_are_created_with_the_section_vector(docs: DocsCollection) -> None:
    """Świeża kolekcja dokumentacji → Qdrant przyjmuje jeden nazwany wektor, a ponowne
    `ensure()` rozpoznaje ją w prawdziwym opisie."""
    assert await docs.ensure() is True
    assert await docs.ensure() is False


async def test_a_section_reads_back_as_the_same_section(docs: DocsCollection) -> None:
    """Zapisana sekcja → odczytana po `section_id`, a jej payload wraca do tej samej
    `DocSection`, z datą i ścieżką rozdziału."""
    await docs.ensure()

    section = SECTIONS[0]
    point   = DocPoint.from_section(section, [0.1, 0.2, 0.3, 0.4])

    assert await docs.upsert([point]) == 1

    stored = (await docs.read_by_id([section.section_id]))[0]

    assert stored.section_id == section.section_id
    assert DocSection.model_validate(stored.payload)            == section
    assert _cosine(stored.vector_section, point.vector_section) == pytest.approx(1.0)


async def test_doc_search_ranks_the_nearest_section_first(docs: DocsCollection) -> None:
    """Wektor zapytania → sekcje w kolejności podobieństwa, z opisem w payloadzie."""
    await docs.ensure()

    near = DocPoint.from_section(SECTIONS[0], [0.1, 0.1, 0.1, 0.1])
    far  = DocPoint.from_section(SECTIONS[1], [0.1, 0.1, -0.1, -0.1])

    await docs.upsert([far, near])

    hits = await docs.search(vector=near.vector_section, limit=5)

    assert [hit.section_id for hit in hits] == [SECTIONS[0].section_id, SECTIONS[1].section_id]
    assert hits[0].payload["title"]         == SECTIONS[0].title
    assert await docs.count()               == 2


async def test_tickets_and_docs_share_one_client(
    client:  QdrantClient,
    tickets: TicketsCollection,
    docs:    DocsCollection,
) -> None:
    """Dwie kolekcje na jednym kliencie → każda widzi tylko swoje punkty, a kolekcja zgłoszeń
    wskazana jako dokumentacja jest odrzucana, bo nie ma wektora `section`."""
    await tickets.ensure()
    await docs.ensure()

    await tickets.upsert([_ticket_point("33644")])

    assert await tickets.count() == 1
    assert await docs.count()    == 0

    with pytest.raises(DbQdrantConfigError):
        await DocsCollection(client, TICKETS_NAME, SIZE).ensure()
