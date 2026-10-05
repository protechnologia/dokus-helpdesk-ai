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
PATH_GROUPS = f"{PATH_QUERY}/groups"
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

DOC_POINT = DocPoint.from_fragment(default_sections()[0], 0, [0.5, 0.6])


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


def _groups(
    *entries: dict,  # np. {"id": "a", "score": 0.74, "payload": {"section_id": "adm-…"}}
) -> httpx.Response:
    """
    Description:
    Odpowiedź Qdranta na wyszukiwanie grup: każdy wpis jako jedyne trafienie swojej grupy.

    Example args:
        entries=({"id": "a", "score": 0.74, "payload": {"section_id": "adm-kancelaria-…"}},)

    Example result:
        httpx.Response(200, json={"result": {"groups": [{"id": "adm-…", "hits": [{…}]}]}})
    """
    groups = [
        {"id": entry["payload"]["section_id"], "hits": [entry]}
        for entry in entries
    ]

    return httpx.Response(200, json={"result": {"groups": groups}})


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
    """Sprawdza, czy obie kolekcje (zgłoszeń i dokumentacji) odmawiają budowy z niedozwoloną nazwą:
    pustą, z samych spacji, z ukośnikiem, ze spacją w środku albo zaczynającą się od cyfry. Błąd
    konfiguracji (`DbQdrantConfigError`) mówi, że chodzi o nazwę kolekcji.

    Wyłapuje kolekcję, która przyjmuje każdą nazwę: nazwa trafia do ścieżki żądania, więc pusta (tak
    Docker Compose podstawia brakującą zmienną) albo z ukośnikiem kierowałaby żądania pod inny
    adres."""
    with pytest.raises(DbQdrantConfigError, match="nazwa kolekcji"):
        kind(QdrantClient(base_url=BASE_URL), name, SIZE)


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
@pytest.mark.parametrize("size", [0, -768])
def test_a_vector_size_below_one_is_refused(kind: type, vectors: tuple, size: int) -> None:
    """Sprawdza, czy obie kolekcje odmawiają budowy z wymiarem wektora równym 0 albo ujemnym (-768):
    błąd konfiguracji nazywa zmienną `EMBEDDING_VECTOR_SIZE`.

    Wyłapuje kolekcję, która przyjmuje taki wymiar: pomyłka w konfiguracji wyszłaby dopiero jako
    odmowa Qdranta przy zakładaniu kolekcji, bez wskazania zmiennej do poprawienia."""
    with pytest.raises(DbQdrantConfigError, match="EMBEDDING_VECTOR_SIZE"):
        kind(QdrantClient(base_url=BASE_URL), NAME, size)


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
def test_the_collection_declares_its_named_vectors(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy każda klasa kolekcji wymienia w `VECTORS` swoje nazwane wektory: kolekcja
    zgłoszeń `problem` i `sts`, a kolekcja dokumentacji `section`.

    Wyłapuje zmienioną nazwę albo liczbę wektorów: to cały schemat kolekcji poza wymiarem, więc po
    takiej zmianie kod przestaje pasować do kolekcji już zbudowanych."""
    assert kind.VECTORS == vectors


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
def test_the_collection_reports_its_name(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy kolekcja oddaje w `name` dokładnie tę nazwę, z którą ją zbudowano (tutaj
    „docs-2026_test").

    Wyłapuje nazwę zmienioną po drodze: wołający wypisuje ją w raporcie i w logach, więc pokazywałby
    inną kolekcję niż ta, na której naprawdę pracuje."""
    collection = kind(QdrantClient(base_url=BASE_URL), "docs-2026_test", SIZE)

    assert collection.name == "docs-2026_test"


# --- ensure -------------------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_a_missing_collection_is_created_with_its_named_vectors(
    kind:    type,
    vectors: tuple,
) -> None:
    """Sprawdza, czy `ensure()` zakłada kolekcję, której w Qdrancie nie ma, i oddaje `True`. Żądanie
    założenia wymienia dokładnie te nazwane wektory, które deklaruje klasa, każdy o wymiarze podanym
    przy budowie (768) i z miarą podobieństwa `Cosine`.

    Wyłapuje kolekcję założoną z innymi wektorami, wymiarem albo miarą: punkty by do niej nie
    pasowały, a próg `RAG_SCORE_MIN` zmierzono na mierze `Cosine`, więc przy innej znaczyłby co
    innego."""
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
    """Sprawdza, czy `ensure()` dla kolekcji, która już istnieje i ma właściwe wektory, oddaje
    `False` i poza odczytem jej opisu nie wysyła żadnego żądania.

    Wyłapuje `ensure()`, które zakłada od nowa albo zmienia istniejącą kolekcję: zwykłe sprawdzenie
    przed indeksacją naruszałoby wtedy gotowy indeks."""
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
    """Sprawdza, czy `ensure()` odrzuca istniejącą kolekcję o wektorach wymiaru 1024, gdy oczekiwany
    wymiar to 768, a błąd konfiguracji podaje obie liczby.

    Wyłapuje sprawdzenie, które kolekcję zbudowaną pod inny model przepuszcza albo po cichu
    dopasowuje (powstałby indeks nieporównywalny z niczym), oraz komunikat z jedną liczbą, z którego
    nie widać, którą stronę poprawić."""
    collection = _collection(kind, routed({("GET", PATH): _description(1024, vectors)}))

    with pytest.raises(DbQdrantConfigError, match="1024") as excinfo:
        await collection.ensure()

    assert "768" in str(excinfo.value)


async def test_tickets_refuse_a_collection_without_sts() -> None:
    """Sprawdza, czy kolekcja zgłoszeń odrzuca istniejącą kolekcję, która ma tylko wektor `problem`:
    błąd konfiguracji nazywa brakujący wektor `sts`.

    Wyłapuje sprawdzenie, które pomija brak jednego z wektorów: zgłoszenia z dwoma wektorami Qdrant
    odrzuciłby dopiero przy zapisie, w środku indeksacji."""
    collection = _collection(
        TicketsCollection,
        routed({("GET", PATH): _description(SIZE, (VECTOR_PROBLEM,))}),
    )

    with pytest.raises(DbQdrantConfigError, match=VECTOR_STS):
        await collection.ensure()


async def test_docs_refuse_a_collection_built_for_tickets() -> None:
    """Sprawdza, czy kolekcja dokumentacji odrzuca istniejącą kolekcję zbudowaną dla zgłoszeń: błąd
    konfiguracji nazywa brakujący wektor `section` i wymienia wektory, które kolekcja ma (`problem`
    i `sts`).

    Wyłapuje pomyłkę w nazwie kolekcji, po której dokumentacja byłaby zapisywana i szukana wśród
    zgłoszeń, oraz komunikat, z którego nie widać, na jaką kolekcję naprawdę trafiono."""
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
    """Sprawdza, czy `ensure()` kończy się naszym błędem konfiguracji z nazwą kolekcji, gdy Qdrant
    oddaje jej opis w nieznanym kształcie (tutaj pusty, bez listy wektorów).

    Wyłapuje odczyt opisu, który na takiej odpowiedzi pada wyjątkiem `KeyError` z głębi kodu:
    z takiego błędu nie widać ani kolekcji, ani tego, że zawiódł jej opis."""
    collection = _collection(
        kind, routed({("GET", PATH): httpx.Response(200, json={"result": {}})})
    )

    with pytest.raises(DbQdrantConfigError, match=NAME):
        await collection.ensure()


# --- upsert -------------------------------------------------------------------------------

async def test_ticket_upsert_sends_named_vectors_and_waits() -> None:
    """Sprawdza, czy zapis jednego zgłoszenia wysyła żądanie `PUT` na ścieżkę punktów kolekcji,
    z punktem w kształcie Qdranta (z nazwanymi wektorami) i z parametrem `wait=true`, a jako wynik
    oddaje 1.

    Wyłapuje zapis, który nie czeka na wykonanie albo wysyła punkt w innym kształcie: indeksacja
    raportuje, ile zapisała, a następny krok od razu to czyta, więc zapis zgłoszony ma być zapisem
    wykonanym."""
    seen: list = []
    collection = _collection(TicketsCollection, capturing(seen))

    written = await collection.upsert([TICKET_POINT])

    assert written == 1

    call = seen[0]

    assert (call["method"], call["path"]) == ("PUT", PATH_POINTS)
    assert call["params"]["wait"]         == "true"
    assert call["body"]["points"]         == [TICKET_POINT.to_qdrant()]


async def test_doc_upsert_sends_the_section_vector() -> None:
    """Sprawdza, czy zapis fragmentu sekcji wysyła punkt z wektorem pod nazwą `section`
    i z identyfikatorem sekcji w danych, a jako wynik oddaje 1.

    Wyłapuje zapis dokumentacji, który wysyła wektor bez nazwy albo gubi opis sekcji: punkt nie
    pasowałby do kolekcji albo trafienia nie dałoby się przypisać do sekcji."""
    seen: list = []
    collection = _collection(DocsCollection, capturing(seen))

    assert await collection.upsert([DOC_POINT]) == 1

    sent = seen[0]["body"]["points"][0]

    assert sent["vector"]                == {VECTOR_SECTION: [0.5, 0.6]}
    assert sent["payload"]["section_id"] == DOC_POINT.section_id


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_upsert_of_nothing_writes_nothing(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy zapis pustej listy punktów oddaje 0 i nie wysyła żadnego żądania, w obu
    kolekcjach.

    Wyłapuje zapis, który przy pustej liście pada albo wysyła puste żądanie: filtr jakości, który
    odrzucił wszystko, to poprawny wynik, a wołający ma go odróżnić od awarii."""
    seen: list = []
    collection = _collection(kind, capturing(seen))

    assert await collection.upsert([]) == 0
    assert seen                        == []


async def test_upsert_splits_into_batches() -> None:
    """Sprawdza, czy zapis 150 punktów idzie w kilku żądaniach, które razem niosą każdy punkt
    dokładnie raz i w kolejności podania, a wynik to 150.

    Wyłapuje zapis jednym wielkim żądaniem, przy którym jedna porażka gubi pracę całej indeksacji,
    oraz podział na partie, który gubi albo powtarza punkty."""
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
    """Sprawdza, czy zapis odrzucony przez Qdranta (status 400) kończy się błędem `DbQdrantError`,
    który niesie wyjaśnienie Qdranta, tutaj „Vector dimension error".

    Wyłapuje odrzucony zapis, który przechodzi bez błędu albo bez podania powodu: indeksacja
    zgłosiłaby zapisane zgłoszenia, których w kolekcji nie ma, albo nie byłoby wiadomo, że zawinił
    np. zły wymiar wektora."""
    collection = _collection(
        TicketsCollection,
        routed({("PUT", PATH_POINTS): httpx.Response(400, text="Vector dimension error")}),
    )

    with pytest.raises(DbQdrantError, match="Vector dimension error"):
        await collection.upsert([TICKET_POINT])


# --- drop i count -------------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_drop_reports_that_a_collection_was_removed(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy `drop()` dla istniejącej kolekcji najpierw pyta, czy ona jest, potem wysyła
    żądanie jej skasowania i oddaje `True`.

    Wyłapuje kasowanie, które zgłasza sukces bez wysłania żądania: przebudowa indeksu zaczyna od
    skasowania kolekcji, więc zostałyby w niej stare punkty."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): _description(SIZE, vectors)}))

    assert await collection.drop() is True
    assert [(call["method"], call["path"]) for call in seen] == [("GET", PATH), ("DELETE", PATH)]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_drop_of_a_missing_collection_is_not_an_error(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy `drop()` dla kolekcji, której nie ma, oddaje `False` i nie wysyła żądania
    skasowania.

    Wyłapuje kasowanie, które przy braku kolekcji pada albo mimo to próbuje ją skasować: brak
    kolekcji to zwykły stan początkowy przebudowy indeksu, a nie awaria."""
    seen: list = []
    collection = _collection(kind, capturing(seen, {("GET", PATH): httpx.Response(404)}))

    assert await collection.drop() is False
    assert [call["method"] for call in seen] == ["GET"]


@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_count_asks_for_an_exact_number(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy `count()` prosi Qdranta o dokładną liczbę punktów (`exact: true` w żądaniu)
    i oddaje liczbę z odpowiedzi, tutaj 171.

    Wyłapuje liczenie przybliżone: liczba punktów mogłaby się wtedy różnić między wywołaniami i nie
    dałoby się nią sprawdzić, że dwie przebudowy indeksu dają ten sam stan."""
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
    """Sprawdza, czy `count()` kończy się błędem `DbQdrantError` z nazwą kolekcji, gdy Qdrant
    odpowiada statusem 200, ale bez licznika.

    Wyłapuje liczenie, które na takiej odpowiedzi pada wyjątkiem `KeyError`: z takiego błędu nie
    widać, że zawiodła odpowiedź Qdranta ani której kolekcji dotyczy."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_COUNT): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.count()


# --- search -------------------------------------------------------------------------------

@pytest.mark.parametrize("vector_name", [VECTOR_PROBLEM, VECTOR_STS])
async def test_ticket_search_asks_the_named_space_it_was_given(vector_name: str) -> None:
    """Sprawdza, czy wyszukiwanie zgłoszeń wysyła do Qdranta dokładnie to, co dostało: wektor
    zapytania, limit 5 i nazwę przestrzeni wektorów w polu `using` (raz `problem`, raz `sts`), a do
    tego prosi o dane karty (`with_payload`).

    Wyłapuje wyszukiwanie, które podmienia albo pomija nazwę przestrzeni: kolekcja ma dwie,
    a szukanie w niewłaściwej nie kończy się błędem, tylko wiarygodnie wyglądającymi złymi
    trafieniami. Wyłapuje też brak prośby o dane, z których powstaje karta zgłoszenia."""
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
    """Sprawdza, czy z odpowiedzi wyszukiwania powstają trafienia z numerem zgłoszenia,
    podobieństwem i identyfikatorem punktu, w tej samej kolejności, w jakiej oddał je Qdrant (tutaj
    0.91 przed 0.42).

    Wyłapuje odczyt, który przestawia trafienia albo myli ich pola: dalszy kod zakłada, że lista
    idzie od najbardziej podobnego, i tak przykłada do niej próg."""
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


async def test_doc_search_asks_for_sections_not_fragments() -> None:
    """Sprawdza, czy wyszukiwanie w dokumentacji prosi Qdranta o grupy punktów po `section_id`, po
    jednym punkcie z grupy, w przestrzeni `section` i z limitem 3, oraz czy z odpowiedzi powstaje
    jedno trafienie na sekcję, z jej identyfikatorem i podobieństwem.

    Wyłapuje wyszukiwanie, które pyta o pojedyncze fragmenty: w kolekcji leżą fragmenty, więc limit
    liczyłby je zamiast sekcji i jedna długa sekcja zajęłaby cały wynik."""
    seen: list = []
    collection = _collection(
        DocsCollection,
        capturing(
            seen,
            {
                ("POST", PATH_GROUPS): _groups(
                    {"id": DOC_POINT.point_id, "score": 0.74, "payload": DOC_POINT.payload}
                )
            },
        ),
    )

    hits = await collection.search(vector=[0.5, 0.6], limit=3)

    assert seen[0]["body"] == {
        "query":        [0.5, 0.6],
        "using":        VECTOR_SECTION,
        "group_by":     "section_id",
        "group_size":   1,
        "limit":        3,
        "with_payload": True,
    }
    assert [hit.section_id for hit in hits] == [DOC_POINT.section_id]
    assert hits[0].score                    == 0.74


async def test_doc_search_with_an_unrecognised_body_fails_with_our_message() -> None:
    """Sprawdza, czy wyszukiwanie w dokumentacji kończy się błędem `DbQdrantError` z nazwą kolekcji,
    gdy Qdrant odpowiada statusem 200, ale bez listy grup.

    Wyłapuje odczyt odpowiedzi, który na nieznanym kształcie pada wyjątkiem `KeyError` dopiero
    dalej, w narzędziu agenta, albo oddaje pustą listę, która wyglądałaby jak brak pasujących
    sekcji."""
    collection = _collection(
        DocsCollection,
        routed({("POST", PATH_GROUPS): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.search(vector=[0.1], limit=5)


async def test_search_finding_nothing_is_an_answer() -> None:
    """Sprawdza, czy wyszukiwanie zgłoszeń, na które Qdrant odpowiada pustą listą, oddaje pustą
    listę trafień, bez wyjątku.

    Wyłapuje wyszukiwanie, które brak trafień traktuje jak błąd: „nie ma podobnych zgłoszeń" to
    poprawna odpowiedź przy nowym typie problemu, a nie awaria."""
    collection = _collection(TicketsCollection, routed({("POST", PATH_QUERY): _hits()}))

    assert await collection.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5) == []


async def test_search_of_an_unknown_named_vector_fails_loudly() -> None:
    """Sprawdza, czy wyszukiwanie z literówką w nazwie wektora („problme"), które Qdrant odrzuca
    statusem 400, kończy się błędem `DbQdrantError` z jego wyjaśnieniem („does not exist").

    Wyłapuje odrzucone wyszukiwanie, które wraca jako pusta lista trafień: wyglądałaby jak „nie ma
    podobnych zgłoszeń" i ukryła pomyłkę w konfiguracji wyszukiwania."""
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
    """Sprawdza, czy wyszukiwanie zgłoszeń kończy się błędem `DbQdrantError` z nazwą kolekcji, gdy
    Qdrant odpowiada statusem 200, ale bez listy trafień.

    Wyłapuje odczyt odpowiedzi, który na nieznanym kształcie pada wyjątkiem `KeyError` dopiero
    dalej, w narzędziu agenta, albo oddaje pustą listę, która wyglądałaby jak brak podobnych
    zgłoszeń."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_QUERY): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.search(vector=[0.1], vector_name=VECTOR_PROBLEM, limit=5)


# --- read_by_id ---------------------------------------------------------------------------

async def test_ticket_read_asks_by_point_ids_with_payload_and_vectors() -> None:
    """Sprawdza, czy odczyt zgłoszenia po numerze „33644" pyta Qdranta o identyfikator punktu
    wyliczony z tego numeru, prosi o dane karty i o wektory, a z odpowiedzi składa cały punkt, taki
    sam jak zapisany.

    Wyłapuje odczyt, który pyta o sam numer zgłoszenia (pod takim identyfikatorem punktu nie ma)
    albo nie prosi o dane karty lub wektory, bez których punktu nie da się złożyć."""
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
    """Sprawdza, czy odczyt po numerach „10718", „33644" i jeszcze raz „10718" oddaje dwa zgłoszenia
    w kolejności numerów z zapytania, choć Qdrant zwrócił je odwrotnie, a powtórzony numer idzie do
    Qdranta i wraca tylko raz.

    Wyłapuje odczyt, który oddaje zgłoszenia w kolejności Qdranta (a on jej nie obiecuje) albo
    powtarza zgłoszenie podane dwa razy: wołający nie mógłby polegać na kolejności, w której
    pytał."""
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
    """Sprawdza, czy odczyt po dwóch numerach, z których jednego („99999") w kolekcji nie ma, oddaje
    samo znalezione zgłoszenie, bez wyjątku.

    Wyłapuje odczyt, który brakujący numer traktuje jak błąd: zgłoszenie bez karty to zwykły stan,
    a o tym, czy brak jest błędem, ma rozstrzygać wołający."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_POINTS): _stored(TICKET_POINT.to_qdrant())}),
    )

    points = await collection.read_by_id(["33644", "99999"])

    assert [point.ticket_id for point in points] == ["33644"]


async def test_reading_nothing_asks_nothing() -> None:
    """Sprawdza, czy odczyt po pustej liście numerów oddaje pustą listę i nie wysyła żadnego
    żądania.

    Wyłapuje odczyt, który przy pustej liście mimo to pyta Qdranta: zbędne żądanie mogłoby skończyć
    się błędem (np. gdy kolekcji jeszcze nie ma), choć nie było czego czytać."""
    seen: list = []
    collection = _collection(TicketsCollection, capturing(seen))

    assert await collection.read_by_id([]) == []
    assert seen                           == []


def test_docs_are_not_read_by_id() -> None:
    """Sprawdza, czy kolekcja dokumentacji nie ma metody odczytu po identyfikatorze (`read_by_id`).

    Wyłapuje dopisanie takiej metody, np. do wspólnej klasy bazowej: sekcja ma w kolekcji kilka
    punktów i z jej identyfikatora nie da się policzyć ile, a treść sekcji czyta się z Postgresa."""
    assert not hasattr(DocsCollection, "read_by_id")


async def test_read_of_a_point_built_otherwise_is_a_config_error() -> None:
    """Sprawdza, czy odczyt zgłoszenia kończy się błędem konfiguracji (`DbQdrantConfigError`)
    nazywającym wektor `problem`, gdy Qdrant oddaje punkt zbudowany jak fragment dokumentacji, czyli
    z wektorem `section` zamiast `problem` i `sts`.

    Wyłapuje kolekcję dokumentacji wskazaną przez pomyłkę jako kolekcja zgłoszeń, która przechodzi
    bez błędu albo pada niejasnym wyjątkiem: taką pomyłkę naprawia zmiana konfiguracji, a nie
    ponowienie odczytu."""
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
    """Sprawdza, czy odczyt zgłoszenia kończy się błędem `DbQdrantError` z nazwą kolekcji, gdy
    Qdrant odpowiada statusem 200, ale zamiast listy punktów oddaje co innego.

    Wyłapuje odczyt, który taką odpowiedź bierze za brak zgłoszenia albo pada niejasnym wyjątkiem:
    z błędu ma być widać, że zawiodła odpowiedź Qdranta i której kolekcji dotyczy."""
    collection = _collection(
        TicketsCollection,
        routed({("POST", PATH_POINTS): httpx.Response(200, json={"result": {}})}),
    )

    with pytest.raises(DbQdrantError, match=NAME):
        await collection.read_by_id(["33644"])


# --- awarie i zamknięcie ------------------------------------------------------------------

@pytest.mark.parametrize("kind, vectors", COLLECTIONS)
async def test_an_unreachable_qdrant_becomes_our_error(kind: type, vectors: tuple) -> None:
    """Sprawdza, czy przy odmowie połączenia z Qdrantem metody `ensure()` i `count()` obu kolekcji
    kończą się naszym błędem `DbQdrantError`.

    Wyłapuje wyjątek biblioteki `httpx` wydostający się z kolekcji: wołający łapią tylko nasz błąd,
    więc niedostępny Qdrant kończyłby się nieobsłużonym wyjątkiem zamiast czytelnego komunikatu."""
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
    """Sprawdza, czy `aclose()` kolekcji zamyka klienta Qdranta, na którym kolekcja stoi, w obu
    kolekcjach.

    Wyłapuje zamknięcie kolekcji, które zostawia otwarte połączenia: kto dostał samą kolekcję, bez
    klienta, nie miałby jak po sobie posprzątać."""
    collection = _collection(kind, capturing([]))

    await collection.aclose()

    assert collection._client._client.is_closed
