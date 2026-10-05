import math
from collections.abc import AsyncIterator

import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.core_model.docs.doc_section import DocSection
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
    """Sprawdza, czy prawdziwy Qdrant przyjmuje kolekcję zgłoszeń z dwoma nazwanymi wektorami:
    pierwsze `ensure()` ją zakłada, a drugie czyta jej opis z Qdranta i odpowiada, że kolekcja
    już jest, zamiast zakładać ją od nowa.

    Wyłapuje żądanie założenia kolekcji, którego Qdrant nie przyjmuje, oraz odczyt opisu
    kolekcji niezgodny z tym, co Qdrant naprawdę oddaje — indeksacja odrzucałaby wtedy własną,
    poprawną kolekcję."""
    assert await tickets.ensure() is True
    assert await tickets.ensure() is False


async def test_a_ticket_reads_back_with_its_payload_and_both_vectors(
    tickets: TicketsCollection,
) -> None:
    """Sprawdza, czy zapisane zgłoszenie da się odczytać po numerze w tym samym kształcie: pod
    identyfikatorem wyliczonym z numeru, z niezmienionymi danymi karty i z każdym z dwóch
    wektorów na swoim miejscu. Wektory porównuje się po kierunku, bo Qdrant przy zapisie zmienia
    ich długość.

    Wyłapuje zapis, który gubi albo zmienia dane karty, trafia pod inny identyfikator albo
    zamienia wektory miejscami. Na tym stoi cała indeksacja: kartę zgłoszenia agent czyta
    właśnie stąd."""
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
    """Sprawdza, czy odczyt po trzech numerach, z których jednego w kolekcji nie ma, oddaje dwa
    zgłoszenia w kolejności numerów z zapytania.

    Wyłapuje odczyt, który oddaje zgłoszenia w kolejności Qdranta (a on jej nie obiecuje) albo
    traktuje brakujący numer jak błąd — tymczasem zgłoszenie bez karty to zwykły stan, nie
    awaria."""
    await tickets.ensure()
    await tickets.upsert([_ticket_point("33644"), _ticket_point("10718")])

    points = await tickets.read_by_id(["10718", "99999", "33644"])

    assert [point.ticket_id for point in points] == ["10718", "33644"]


async def test_reupserting_the_same_ticket_overwrites_it(tickets: TicketsCollection) -> None:
    """Sprawdza, czy to samo zgłoszenie zapisane dwa razy, za drugim razem z innymi wektorami,
    zostaje w kolekcji jako jeden punkt.

    Wyłapuje zapis, który przy powtórzeniu dokłada drugi punkt: ponowna indeksacja dublowałaby
    wtedy zgłoszenia, zamiast je nadpisywać."""
    await tickets.ensure()

    await tickets.upsert([_ticket_point("33644", fill=0.1)])
    await tickets.upsert([_ticket_point("33644", fill=0.9)])

    assert await tickets.count() == 1


async def test_a_wrong_vector_size_is_refused_against_a_real_collection(
    client:  QdrantClient,
    tickets: TicketsCollection,
) -> None:
    """Sprawdza, czy kolekcja założona z wektorami o wymiarze 4 jest odrzucana błędem
    konfiguracji (`DbQdrantConfigError`), gdy ktoś wskaże ją z wymiarem 5. Wymiar istniejącej
    kolekcji jest czytany z opisu, który oddaje prawdziwy Qdrant i którego kształtu nie ustala
    nasz kod.

    Wyłapuje sprawdzenie wymiaru, które nie rozumie prawdziwego opisu kolekcji i przepuszcza
    niezgodność: wyszłaby ona dopiero w środku indeksacji, jako punkty odrzucone przez Qdranta."""
    await tickets.ensure()

    with pytest.raises(DbQdrantConfigError):
        await TicketsCollection(client, TICKETS_NAME, SIZE + 1).ensure()


async def test_search_ranks_the_nearest_ticket_first(tickets: TicketsCollection) -> None:
    """Sprawdza, czy wyszukiwanie po wektorze oddaje zgłoszenia od najbardziej podobnego: z dwóch
    zapisanych pierwsze jest to, którego wektor ma ten sam kierunek co zapytanie; ma ono wyższe
    podobieństwo i niesie dane swojej karty.

    Wyłapuje wyszukiwanie, które oddaje trafienia w złej kolejności albo bez danych karty.
    Sortuje Qdrant, nie nasz kod, więc dowieść tego może tylko test na działającej usłudze."""
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
    """Sprawdza, czy wyszukiwanie szuka w tej z dwóch przestrzeni wektorów, którą wskazano: ten
    sam wektor zapytania daje podobieństwo 1 wobec wektora `problem` i -1 wobec wektora `sts`
    tego samego zgłoszenia, bo w teście oba mają przeciwne kierunki.

    Wyłapuje wyszukiwanie, które pomija podaną nazwę wektora i szuka w niewłaściwej przestrzeni.
    Taka pomyłka sama się nie ujawnia: obie przestrzenie odpowiadają, a zła oddaje wiarygodnie
    wyglądające trafienia."""
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
    """Sprawdza, czy wyszukiwanie z literówką w nazwie wektora („problme" zamiast „problem")
    kończy się błędem (`DbQdrantError`), bo tak odpowiada na nią prawdziwy Qdrant.

    Wyłapuje literówkę, która wraca jako pusta lista trafień: wyglądałaby jak „nie ma podobnych
    zgłoszeń", choć wyszukiwanie w ogóle się nie odbyło."""
    await tickets.ensure()
    await tickets.upsert([_ticket_point("33644")])

    with pytest.raises(DbQdrantError):
        await tickets.search(vector=[0.1] * SIZE, vector_name="problme", limit=5)


async def test_reading_from_a_missing_collection_is_an_error(tickets: TicketsCollection) -> None:
    """Sprawdza, czy odczyt zgłoszenia i liczenie punktów w kolekcji, której nie ma, kończą się
    błędem (`DbQdrantError`), a nie pustym wynikiem.

    Wyłapuje brak kolekcji przemilczany jako pusta lista albo zero: wyglądałoby to jak „nie ma
    takiego zgłoszenia", choć w rzeczywistości nie ma całego indeksu."""
    with pytest.raises(DbQdrantError):
        await tickets.read_by_id(["33644"])

    with pytest.raises(DbQdrantError):
        await tickets.count()


async def test_dropping_removes_the_collection(tickets: TicketsCollection) -> None:
    """Sprawdza, czy kasowanie naprawdę usuwa kolekcję z Qdranta: pierwsze `drop()` odpowiada, że
    skasowało, a drugie, że nie było już czego kasować.

    Wyłapuje kasowanie, które zgłasza sukces, a kolekcję zostawia, albo pada, gdy kolekcji nie
    ma. Przebudowa indeksu zaczyna od skasowania, więc zostałyby w nim stare zgłoszenia."""
    await tickets.ensure()

    assert await tickets.drop() is True
    assert await tickets.drop() is False


# --- dokumentacja -------------------------------------------------------------------------

async def test_docs_are_created_with_the_section_vector(docs: DocsCollection) -> None:
    """Sprawdza, czy prawdziwy Qdrant przyjmuje kolekcję dokumentacji z jednym nazwanym wektorem:
    pierwsze `ensure()` ją zakłada, a drugie rozpoznaje ją w opisie z Qdranta i odpowiada, że
    kolekcja już jest.

    Wyłapuje żądanie założenia kolekcji, którego Qdrant nie przyjmuje, oraz odczyt opisu
    kolekcji niezgodny z tym, co Qdrant naprawdę oddaje — indeksacja dokumentacji odrzucałaby
    wtedy własną, poprawną kolekcję."""
    assert await docs.ensure() is True
    assert await docs.ensure() is False


async def test_fragments_of_a_section_come_back_as_one_section(docs: DocsCollection) -> None:
    """Sprawdza, czy sekcja zapisana jako dwa fragmenty, czyli dwa punkty w kolekcji, wraca
    z wyszukiwania raz: jako jedno trafienie, z fragmentem najbliższym zapytaniu. Sprawdza też,
    czy z danych trafienia da się odtworzyć opis sekcji (`DocSection`) razem z datą i ścieżką
    rozdziału.

    Wyłapuje wyszukiwanie, które oddaje tę samą sekcję kilka razy albo nie z tym fragmentem,
    oraz zapis, po którym opisu sekcji nie da się już złożyć — agent dostałby powtórzenia
    zamiast listy różnych sekcji."""
    await docs.ensure()

    section = SECTIONS[0]
    first   = DocPoint.from_fragment(section, 0, [0.1, 0.2, 0.3, 0.4])
    second  = DocPoint.from_fragment(section, 1, [0.4, 0.3, 0.2, 0.1])

    assert await docs.upsert([first, second]) == 2
    assert await docs.count()                 == 2

    hits = await docs.search(vector=second.vector_section, limit=5)

    assert [hit.point_id for hit in hits]           == [second.point_id]
    assert DocSection.model_validate(hits[0].payload) == section


async def test_a_long_section_does_not_crowd_out_the_others(docs: DocsCollection) -> None:
    """Sprawdza, czy limit wyników liczy sekcje, a nie fragmenty: jedna sekcja ma tu pięć
    fragmentów bliższych zapytaniu niż jedyny fragment drugiej sekcji, a przy limicie 2 wracają
    obie sekcje.

    Wyłapuje wyszukiwanie, w którym długa sekcja zajmuje cały wynik swoimi fragmentami, a inne
    pasujące sekcje nie docierają do agenta."""
    await docs.ensure()

    long_section = [
        DocPoint.from_fragment(SECTIONS[0], number, [0.4, 0.3, 0.2, 0.1 + number / 100])
        for number in range(5)
    ]
    short_section = DocPoint.from_fragment(SECTIONS[1], 0, [0.1, 0.2, 0.3, 0.4])

    await docs.upsert([*long_section, short_section])

    hits = await docs.search(vector=[0.4, 0.3, 0.2, 0.1], limit=2)

    assert [hit.section_id for hit in hits] == [SECTIONS[0].section_id, SECTIONS[1].section_id]


async def test_reimporting_the_same_fragment_overwrites_it(docs: DocsCollection) -> None:
    """Sprawdza, czy ten sam fragment sekcji zapisany dwa razy, za drugim razem z innym wektorem,
    zostaje w kolekcji jako jeden punkt, bo jego identyfikator wynika z sekcji i numeru
    fragmentu.

    Wyłapuje identyfikator punktu, który zmienia się między zapisami: powtórzony zapis
    zostawiałby wtedy w kolekcji kilka kopii tego samego fragmentu."""
    await docs.ensure()

    await docs.upsert([DocPoint.from_fragment(SECTIONS[0], 0, [0.1, 0.2, 0.3, 0.4])])
    await docs.upsert([DocPoint.from_fragment(SECTIONS[0], 0, [0.4, 0.3, 0.2, 0.1])])

    assert await docs.count() == 1


async def test_doc_search_ranks_the_nearest_section_first(docs: DocsCollection) -> None:
    """Sprawdza, czy wyszukiwanie w dokumentacji oddaje sekcje od najbardziej podobnej: z dwóch
    zapisanych pierwsza jest ta, której wektor ma kierunek zapytania, choć zapisano ją jako
    drugą, i niesie w danych swój tytuł.

    Wyłapuje wyszukiwanie, które przy zwijaniu fragmentów do sekcji gubi kolejność podobieństwa
    albo opis sekcji — agent czytałby wtedy najpierw mniej pasujące sekcje."""
    await docs.ensure()

    near = DocPoint.from_fragment(SECTIONS[0], 0, [0.1, 0.1, 0.1, 0.1])
    far  = DocPoint.from_fragment(SECTIONS[1], 0, [0.1, 0.1, -0.1, -0.1])

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
    """Sprawdza, czy dwie kolekcje na jednym kliencie nie mieszają się ze sobą: po zapisie
    jednego zgłoszenia kolekcja zgłoszeń ma jeden punkt, a kolekcja dokumentacji zero. Sprawdza
    też, czy kolekcja zgłoszeń wskazana jako kolekcja dokumentacji jest odrzucana błędem
    konfiguracji, bo nie ma wektora `section`.

    Wyłapuje zapis trafiający do niewłaściwej kolekcji oraz pomyłkę w nazwie kolekcji, po której
    dokumentacja byłaby szukana wśród zgłoszeń."""
    await tickets.ensure()
    await docs.ensure()

    await tickets.upsert([_ticket_point("33644")])

    assert await tickets.count() == 1
    assert await docs.count()    == 0

    with pytest.raises(DbQdrantConfigError):
        await DocsCollection(client, TICKETS_NAME, SIZE).ensure()
