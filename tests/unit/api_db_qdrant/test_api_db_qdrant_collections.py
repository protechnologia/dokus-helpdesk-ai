import httpx
import pytest

from app.agent_tools.docs.fake_docs import default_sections
from app.db_qdrant import (
    VECTOR_PROBLEM,
    VECTOR_SECTION,
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
from tests.helpers_transport import capturing, raising, routed, with_transport

# Kolekcje testowane bez usługi, na prawdziwym kliencie z podmienionym transportem: sprawdzamy,
# CO idzie do Qdranta i jak czytamy odpowiedź. Że Qdrant odpowiada na to tak, jak zakładamy,
# sprawdza test na stacku.

BASE_URL = "http://qdrant:6333"
NAME     = "tickets"
SIZE     = 768

# Ścieżki, po których rozchodzą się odpowiedzi atrapy — zapisane raz.
PATH        = f"/collections/{NAME}"
PATH_POINTS = f"{PATH}/points"
PATH_QUERY  = f"{PATH_POINTS}/query"
PATH_COUNT  = f"{PATH_POINTS}/count"

# Obie kolekcje z ich schematem: to, co wspólne, sprawdzamy na każdej.
COLLECTIONS = [
    pytest.param(TicketsCollection, (VECTOR_PROBLEM, VECTOR_STS), id="tickets"),
    pytest.param(DocsCollection,    (VECTOR_SECTION,),            id="docs"),
]

# Punkt zbudowany ręcznie, nie z `ParsedTicket`: ten plik testuje kolekcję, a zmiana schematu
# karty nie ma go psuć.
TICKET_POINT = TicketPoint(
    point_id       = point_id_for("33644"),
    vector_problem = [0.1, -0.2],
    vector_sts     = [0.3, -0.4],
    payload        = {"ticket_id": "33644"},
)

DOC_POINT = DocPoint.from_section(default_sections()[0], [0.5, 0.6])


def _collection(
    kind:    type,                 # np. TicketsCollection
    handler: httpx.MockTransport,  # np. routed({("GET", PATH): httpx.Response(404)})
) -> TicketsCollection | DocsCollection:
    """
    Description:
    Buduje kolekcję o wymiarze `SIZE` na kliencie odpowiadającym z atrapy transportu zamiast
    z gniazda.

    Example args:
        kind=TicketsCollection
        handler=routed({("GET", "/collections/tickets"): httpx.Response(404)})

    Example result:
        TicketsCollection „tickets" odpowiadająca z atrapy
    """
    client = with_transport(QdrantClient(base_url=BASE_URL), handler)

    return kind(client, NAME, SIZE)


def _description(
    size:  int,              # np. 768
    names: tuple[str, ...],  # np. ("problem", "sts")
) -> httpx.Response:
    """
    Description:
    Opis istniejącej kolekcji, jaki oddaje Qdrant: podane nazwane wektory o podanym wymiarze.

    Example args:
        size=768
        names=("problem", "sts")

    Example result:
        httpx.Response(200, json={"result": {"config": {"params": {"vectors": {…}}}}})
    """
    vectors = {name: {"size": size, "distance": "Cosine"} for name in names}

    return httpx.Response(200, json={"result": {"config": {"params": {"vectors": vectors}}}})


def _hits(
    *entries: dict,  # np. {"id": "a", "score": 0.87, "payload": {"ticket_id": "33644"}}
) -> httpx.Response:
    """
    Description:
    Odpowiedź Qdranta na wyszukiwanie: wpisy w zagnieżdżeniu, którego używa końcówka zapytań.

    Example args:
        entries=({"id": "a", "score": 0.87, "payload": {"ticket_id": "33644"}},)

    Example result:
        httpx.Response(200, json={"result": {"points": [{…}]}})
    """
    return httpx.Response(200, json={"result": {"points": list(entries)}})


def _stored(
    *entries: dict,  # np. TICKET_POINT.to_qdrant()
) -> httpx.Response:
    """
    Description:
    Odpowiedź Qdranta na odczyt po identyfikatorach: lista punktów z payloadem i wektorami.

    Example args:
        entries=(TICKET_POINT.to_qdrant(),)

    Example result:
        httpx.Response(200, json={"result": [{"id": "df3b…", "vector": {…}, "payload": {…}}]})
    """
    return httpx.Response(200, json={"result": list(entries)})


# --- budowa -------------------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
@pytest.mark.parametrize("name", ["", "   ", "tickets/points", "tickets test", "1tickets"])
def test_a_name_outside_the_pattern_is_refused(kind: type, vectors: tuple, name: str) -> None:
    """Nazwa pusta, ze spacją, z ukośnikiem albo od cyfry → błąd przy budowie: nazwa trafia do
    ścieżki żądania, a pusta (tak compose podstawia brak zmiennej) pisałaby pod inny adres."""
    with pytest.raises(DbQdrantConfigError, match="nazwa kolekcji"):
        kind(QdrantClient(base_url=BASE_URL), name, SIZE)


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
@pytest.mark.parametrize("size", [0, -768])
def test_a_vector_size_below_one_is_refused(kind: type, vectors: tuple, size: int) -> None:
    """Wymiar zerowy albo ujemny → błąd przy budowie, a nie odmowa Qdranta przy zakładaniu
    kolekcji."""
    with pytest.raises(DbQdrantConfigError, match="EMBEDDING_VECTOR_SIZE"):
        kind(QdrantClient(base_url=BASE_URL), NAME, size)


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
def test_the_collection_declares_its_named_vectors(kind: type, vectors: tuple) -> None:
    """Klasa kolekcji → jej nazwane wektory w `VECTORS`: to cały schemat poza wymiarem."""
    assert kind.VECTORS == vectors


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
def test_the_collection_reports_its_name(kind: type, vectors: tuple) -> None:
    """Kolekcja → oddaje nazwę, którą dostała; wołający wypisuje ją w raporcie i logach."""
    collection = kind(QdrantClient(base_url=BASE_URL), "docs-2026_test", SIZE)

    assert collection.name == "docs-2026_test"


# --- ensure -------------------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_a_missing_collection_is_created_with_its_named_vectors(
    kind:    type,
    vectors: tuple,
) -> None:
    """Brak kolekcji → założona z dokładnie tymi nazwanymi wektorami, które deklaruje klasa,
    każdy w wymiarze podanym przy budowie i z metryką Cosine — na niej mierzono
    `RAG_SCORE_MIN`."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): httpx.Response(404)}))

    created = await collection.ensure()

    assert created is True

    write = next(call for call in seen if call["method"] == "PUT")

    assert write["path"] == PATH
    assert write["body"]["vectors"] == {
        name: {"size": SIZE, "distance": "Cosine"} for name in vectors
    }


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_a_matching_collection_is_left_alone(kind: type, vectors: tuple) -> None:
    """Kolekcja zgodna → „już była" i żadnego zapisu."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): _description(SIZE, vectors)}))

    created = await collection.ensure()

    assert created is False
    assert [call["method"] for call in seen] == ["GET"]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_a_wrong_vector_size_is_refused_with_both_numbers(
    kind:    type,
    vectors: tuple,
) -> None:
    """Kolekcja zbudowana pod inny model → błąd konfiguracji z OBIEMA liczbami: jedna z nich
    nie mówi, którą stronę poprawić. Cicha naprawa dałaby indeks nieporównywalny z niczym."""
    collection = _collection(kind, routed({("GET", PATH): _description(1024, vectors)}))

    with pytest.raises(DbQdrantConfigError, match="1024") as excinfo:
        await collection.ensure()

    assert "768" in str(excinfo.value)


async def test_tickets_refuse_a_collection_without_sts() -> None:
    """Kolekcja zgłoszeń z samym `problem` → błąd konfiguracji nazywający brakujący wektor."""
    collection = _collection(
        TicketsCollection,
        routed({("GET", PATH): _description(SIZE, (VECTOR_PROBLEM,))}),
    )

    with pytest.raises(DbQdrantConfigError, match=VECTOR_STS):
        await collection.ensure()


async def test_docs_refuse_a_collection_built_for_tickets() -> None:
    """Kolekcja dokumentacji wskazująca kolekcję zgłoszeń → błąd konfiguracji: nie ma w niej
    wektora `section`, a komunikat wymienia te, które są."""
    collection = _collection(
        DocsCollection,
        routed({("GET", PATH): _description(SIZE, (VECTOR_PROBLEM, VECTOR_STS))}),
    )

    with pytest.raises(DbQdrantConfigError, match=VECTOR_SECTION) as excinfo:
        await collection.ensure()

    assert "problem, sts" in str(excinfo.value)


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_an_unrecognised_description_fails_with_our_message(
    kind:    type,
    vectors: tuple,
) -> None:
    """Opis kolekcji w nieznanym kształcie → nasz błąd konfiguracji z nazwą kolekcji, nigdy
    `KeyError` z trzeciego poziomu odpowiedzi."""
    collection = _collection(
        kind, routed({("GET", PATH): httpx.Response(200, json={"result": {}})})
    )

    with pytest.raises(DbQdrantConfigError, match=NAME):
        await collection.ensure()


# --- upsert -------------------------------------------------------------------------------

async def test_ticket_upsert_sends_named_vectors_and_waits() -> None:
    """Punkty zgłoszeń → na drucie nazwane wektory i `wait=true`: zapis zgłoszony to zapis
    wykonany, bo przebieg raportuje, co zapisał, a kolejny krok to czyta."""
    seen: list = []
    collection = _collection(TicketsCollection, capturing(seen))

    written = await collection.upsert([TICKET_POINT])

    assert written == 1

    call = seen[0]

    assert (call["method"], call["path"]) == ("PUT", PATH_POINTS)
    assert call["params"]["wait"]         == "true"
    assert call["body"]["points"]         == [TICKET_POINT.to_qdrant()]


async def test_doc_upsert_sends_the_section_vector() -> None:
    """Punkt sekcji → na drucie wektor pod nazwą `section` i opis sekcji w payloadzie."""
    seen: list = []
    collection = _collection(DocsCollection, capturing(seen))

    assert await collection.upsert([DOC_POINT]) == 1

    sent = seen[0]["body"]["points"][0]

    assert sent["vector"]                == {VECTOR_SECTION: [0.5, 0.6]}
    assert sent["payload"]["section_id"] == DOC_POINT.section_id


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_upsert_of_nothing_writes_nothing(kind: type, vectors: tuple) -> None:
    """Pusta lista → zero zapisanych i żadnego żądania: filtr, który odrzucił wszystko, to
    poprawny wynik, a wołający ma go odróżnić od awarii."""
    seen: list = []
    collection = _collection(kind, capturing(seen))

    assert await collection.upsert([]) == 0
    assert seen                        == []


async def test_upsert_splits_into_batches() -> None:
    """Więcej punktów niż jedna partia → kilka żądań, razem niosących każdy punkt dokładnie
    raz. Jedno wielkie żądanie oddawałoby pracę całego przebiegu jednej porażce."""
    seen: list = []
    collection = _collection(TicketsCollection, capturing(seen))
    points     = [
        TICKET_POINT.model_copy(update={"point_id": f"id-{index}"}) for index in range(150)
    ]

    written = await collection.upsert(points)

    assert written   == 150
    assert len(seen) > 1

    sent = [point["id"] for call in seen for point in call["body"]["points"]]

    assert sent == [f"id-{index}" for index in range(150)]


async def test_a_rejected_upsert_carries_qdrants_explanation() -> None:
    """Qdrant odrzuca zapis (zły wymiar, nieznana nazwa wektora) → błąd niesie jego powód."""
    collection = _collection(
        TicketsCollection,
        routed({("PUT", PATH_POINTS): httpx.Response(400, text="Vector dimension error")}),
    )

    with pytest.raises(DbQdrantError, match="Vector dimension error"):
        await collection.upsert([TICKET_POINT])


# --- drop i count -------------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_drop_reports_that_a_collection_was_removed(kind: type, vectors: tuple) -> None:
    """Istniejąca kolekcja → skasowana, wynik True."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): _description(SIZE, vectors)}))

    assert await collection.drop() is True
    assert [(call["method"], call["path"]) for call in seen] == [("GET", PATH), ("DELETE", PATH)]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_drop_of_a_missing_collection_is_not_an_error(kind: type, vectors: tuple) -> None:
    """Brak kolekcji → False i żadnego DELETE: to zwykły stan początkowy przebudowy."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): httpx.Response(404)}))

    assert await collection.drop() is False
    assert [call["method"] for call in seen] == ["GET"]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_count_asks_for_an_exact_number(kind: type, vectors: tuple) -> None:
    """`count()` → `exact: true` na drucie; liczba przybliżona rozchwiałaby asercję „dwie
    przebudowy dają ten sam stan"."""
    seen: list = []
    collection = _collection(
        kind,
        capturing(
            seen,
            {("POST", PATH_COUNT): httpx.Response(200, json={"result": {"count": 171}})},
        ),
    )

    assert await collection.count() == 171
    assert seen[0]["body"]["exact"] is True


async def test_count_with_an_unrecognised_body_fails_with_our_message() -> None:
    """200 bez licznika → `DbQdrantError` z nazwą kolekcji, a nie `KeyError`."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_COUNT): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.count()


# --- search -------------------------------------------------------------------------------

@pytest.mark.parametrize("vector_name", [VECTOR_PROBLEM, VECTOR_STS])
async def test_ticket_search_asks_the_named_space_it_was_given(vector_name: str) -> None:
    """`search(vector_name=…)` → ta sama nazwa w `using` na drucie. Kolekcja ma dwie przestrzenie,
    a szukanie po niewłaściwej oddaje wiarygodne bzdury zamiast błędu, więc nazwa musi dojść
    dokładnie taka, jak ją podano — i z payloadem, bo z niego powstaje karta."""
    seen: list = []
    collection = _collection(TicketsCollection, capturing(seen, {("POST", PATH_QUERY): _hits()}))

    await collection.search(vector=[0.1, -0.2], vector_name=vector_name, limit=5)

    assert seen[0]["body"] == {
        "query":        [0.1, -0.2],
        "using":        vector_name,
        "limit":        5,
        "with_payload": True,
    }


async def test_ticket_search_returns_hits_in_the_order_qdrant_gave_them() -> None:
    """Odpowiedź wyszukiwania → trafienia z podobieństwem, identyfikatorem i payloadem,
    w kolejności Qdranta: próg dalej czyta od najlepszego."""
    collection = _collection(
        TicketsCollection,
        routed(
            {
                ("POST", PATH_QUERY): _hits(
                    {"id": "a", "score": 0.91, "payload": {"ticket_id": "33644"}},
                    {"id": "b", "score": 0.42, "payload": {"ticket_id": "10718"}},
                )
            }
        ),
    )

    hits = await collection.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5)

    assert [hit.ticket_id for hit in hits] == ["33644", "10718"]
    assert [hit.score for hit in hits]     == [0.91, 0.42]
    assert hits[0].point_id                == "a"


async def test_doc_search_asks_the_section_space() -> None:
    """`search()` dokumentacji → `using: section` bez podawania nazwy: wektor jest jeden,
    a trafienie niesie identyfikator sekcji."""
    seen: list = []
    collection = _collection(
        DocsCollection,
        capturing(
            seen,
            {
                ("POST", PATH_QUERY): _hits(
                    {"id": DOC_POINT.point_id, "score": 0.74, "payload": DOC_POINT.payload}
                )
            },
        ),
    )

    hits = await collection.search(vector=[0.5, 0.6], limit=3)

    assert seen[0]["body"]["using"] == VECTOR_SECTION
    assert seen[0]["body"]["limit"] == 3
    assert hits[0].section_id       == DOC_POINT.section_id
    assert hits[0].score            == 0.74


async def test_search_finding_nothing_is_an_answer() -> None:
    """Pusty wynik → pusta lista, nie błąd: „nowy typ problemu" to poprawna odpowiedź."""
    collection = _collection(TicketsCollection, routed({("POST", PATH_QUERY): _hits()}))

    assert await collection.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5) == []


async def test_search_of_an_unknown_named_vector_fails_loudly() -> None:
    """Qdrant odrzuca nieznaną nazwę wektora → `DbQdrantError` z jego wyjaśnieniem, nigdy pusta
    lista: ta wyglądałaby jak „nic podobnego" i ukryła błąd okablowania."""
    collection = _collection(
        TicketsCollection,
        routed(
            {
                ("POST", PATH_QUERY): httpx.Response(
                    400, text="Wrong input: Vector name error: vector 'problme' does not exist"
                )
            }
        ),
    )

    with pytest.raises(DbQdrantError, match="does not exist"):
        await collection.search(vector=[0.1], vector_name="problme", limit=5)


async def test_search_with_an_unrecognised_body_fails_with_our_message() -> None:
    """200 w nieznanym kształcie → `DbQdrantError` z nazwą kolekcji, a nie `KeyError` gdzieś
    dalej w narzędziu."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_QUERY): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5)


# --- read_by_id ---------------------------------------------------------------------------

async def test_ticket_read_asks_by_point_ids_with_payload_and_vectors() -> None:
    """Numery zgłoszeń → na drucie identyfikatory punktów wyliczone z numerów, z prośbą
    o payload i wektory: odczyt oddaje cały punkt."""
    seen: list = []
    collection = _collection(
        TicketsCollection,
        capturing(seen, {("POST", PATH_POINTS): _stored(TICKET_POINT.to_qdrant())}),
    )

    points = await collection.read_by_id(["33644"])

    assert seen[0]["body"] == {
        "ids":          [point_id_for("33644")],
        "with_payload": True,
        "with_vector":  True,
    }
    assert points == [TICKET_POINT]


async def test_read_returns_points_in_the_order_they_were_asked_for() -> None:
    """Qdrant oddaje punkty w swojej kolejności → wynik w kolejności numerów z zapytania,
    a numer podany dwa razy wraca raz."""
    other      = TICKET_POINT.model_copy(
        update={"point_id": point_id_for("10718"), "payload": {"ticket_id": "10718"}}
    )
    seen: list = []
    collection = _collection(
        TicketsCollection,
        capturing(
            seen,
            {("POST", PATH_POINTS): _stored(TICKET_POINT.to_qdrant(), other.to_qdrant())},
        ),
    )

    points = await collection.read_by_id(["10718", "33644", "10718"])

    assert [point.ticket_id for point in points] == ["10718", "33644"]
    assert seen[0]["body"]["ids"] == [point_id_for("10718"), point_id_for("33644")]


async def test_a_ticket_missing_from_the_collection_is_missing_from_the_result() -> None:
    """Numer, którego w kolekcji nie ma → po prostu brak go w wyniku; o tym, czy to błąd,
    rozstrzyga wołający."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_POINTS): _stored(TICKET_POINT.to_qdrant())}),
    )

    points = await collection.read_by_id(["33644", "99999"])

    assert [point.ticket_id for point in points] == ["33644"]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_reading_nothing_asks_nothing(kind: type, vectors: tuple) -> None:
    """Pusta lista identyfikatorów → pusty wynik bez żądania."""
    seen: list = []
    collection = _collection(kind, capturing(seen))

    assert await collection.read_by_id([]) == []
    assert seen                           == []


async def test_doc_read_asks_by_section_ids() -> None:
    """Identyfikatory sekcji → punkty sekcji, z opisem i wektorem, pod identyfikatorem
    wyliczonym z `section_id`."""
    seen: list = []
    collection = _collection(
        DocsCollection,
        capturing(seen, {("POST", PATH_POINTS): _stored(DOC_POINT.to_qdrant())}),
    )

    points = await collection.read_by_id([DOC_POINT.section_id])

    assert seen[0]["body"]["ids"] == [point_id_for(DOC_POINT.section_id)]
    assert points                 == [DOC_POINT]


async def test_read_of_a_point_built_otherwise_is_a_config_error() -> None:
    """Kolekcja dokumentacji czytana jak zgłoszenia → błąd konfiguracji: punkt nie ma wektorów
    `problem` i `sts`."""
    collection = _collection(
        TicketsCollection,
        routed(
            {
                ("POST", PATH_POINTS): _stored(
                    {**DOC_POINT.to_qdrant(), "id": point_id_for("33644")}
                )
            }
        ),
    )

    with pytest.raises(DbQdrantConfigError, match=VECTOR_PROBLEM):
        await collection.read_by_id(["33644"])


async def test_read_with_an_unrecognised_body_fails_with_our_message() -> None:
    """200 w nieznanym kształcie → `DbQdrantError` z nazwą kolekcji."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_POINTS): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.read_by_id(["33644"])


# --- awarie i zamknięcie ------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_an_unreachable_qdrant_becomes_our_error(kind: type, vectors: tuple) -> None:
    """Odmowa połączenia → `DbQdrantError` z każdej metody kolekcji, nigdy typ `httpx`."""
    collection = _collection(kind, raising(httpx.ConnectError("connection refused")))

    with pytest.raises(DbQdrantError):
        await collection.ensure()

    with pytest.raises(DbQdrantError):
        await collection.count()


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_aclose_closes_the_client_the_collection_stands_on(
    kind:    type,
    vectors: tuple,
) -> None:
    """`aclose()` kolekcji → zamknięty klient: kto dostał samą kolekcję, może po sobie
    posprzątać."""
    collection = _collection(kind, capturing([]))

    await collection.aclose()

    assert collection._client._client.is_closed
