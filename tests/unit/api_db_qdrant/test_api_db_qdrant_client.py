import httpx
import pytest

from app.db_qdrant import DbQdrantConfigError, DbQdrantError, QdrantClient
from tests.helpers_transport import always, capturing, raising, routed, with_transport

# Klient testowany bez usługi: transport odpowiada, zapisuje albo pada zamiast gniazda. Sprawdzamy
# tylko rozmowę — co idzie na drut i jak awaria staje się naszym błędem. Co znaczą żądania,
# sprawdzają testy kolekcji.

BASE_URL = "http://qdrant:6333"
PATH     = "/collections/tickets"


def _client(
    handler: httpx.MockTransport,  # np. always({"result": True})
) -> QdrantClient:
    """
    Description:
    Buduje klienta odpowiadającego z atrapy transportu zamiast z gniazda.

    Example args:
        handler=always({"result": True})

    Example result:
        QdrantClient odpowiadający z atrapy
    """
    return with_transport(QdrantClient(base_url=BASE_URL), handler)


# --- budowa -------------------------------------------------------------------------------

@pytest.mark.parametrize("blank", ["", "   "])
def test_empty_base_url_is_refused_at_build_time(blank: str) -> None:
    """Sprawdza, czy budowa klienta z pustym adresem Qdranta (pusty tekst albo same spacje) kończy
    się od razu błędem konfiguracji (`DbQdrantConfigError`), który nazywa zmienną `QDRANT_URL`.

    Wyłapuje klienta, który przyjmuje pusty adres: tak Docker Compose podstawia brakującą zmienną,
    a pomyłka wyszłaby dopiero w środku przebiegu, jako niejasny błąd połączenia."""
    with pytest.raises(DbQdrantConfigError, match="QDRANT_URL"):
        QdrantClient(base_url=blank)


# --- request ------------------------------------------------------------------------------

async def test_request_sends_what_it_was_given_and_returns_the_body() -> None:
    """Sprawdza, czy `request()` wysyła do Qdranta jedno żądanie z dokładnie tą metodą, ścieżką,
    parametrami i treścią, które dostało, a odpowiedź oddaje jako słownik.

    Wyłapuje klienta, który po drodze gubi albo zmienia część żądania (np. parametr `wait`) lub
    odpowiedź: kolekcje same składają żądania i polegają na tym, że dojdą one bez zmian."""
    seen: list = []
    client     = _client(
        capturing(seen, {("PUT", PATH): httpx.Response(200, json={"result": True})})
    )

    body = await client.request("PUT", PATH, params={"wait": "true"}, json={"points": []})

    assert body == {"result": True}
    assert seen == [
        {"method": "PUT", "path": PATH, "params": {"wait": "true"}, "body": {"points": []}}
    ]


async def test_rejected_request_carries_qdrants_explanation() -> None:
    """Sprawdza, czy żądanie odrzucone przez Qdranta (status 400) kończy się błędem `DbQdrantError`,
    który niesie wyjaśnienie z treści odpowiedzi, tutaj „Vector dimension error".

    Wyłapuje błąd bez wyjaśnienia Qdranta: to jedyne miejsce, które mówi, dlaczego żądanie zostało
    odrzucone, więc bez niego nie byłoby wiadomo, co poprawić."""
    client = _client(always(status=400, text="Wrong input: Vector dimension error"))

    with pytest.raises(DbQdrantError, match="Vector dimension error"):
        await client.request("PUT", f"{PATH}/points", json={"points": []})


async def test_missing_resource_is_an_error_for_request() -> None:
    """Sprawdza, czy status 404 w odpowiedzi na zwykłe żądanie `request()` (tutaj liczenie punktów
    kolekcji) kończy się błędem `DbQdrantError` z numerem statusu.

    Wyłapuje klienta, który każde 404 czyta jako zwykłą odpowiedź „nie ma": tak wolno czytać tylko
    odczytowi `get_or_none()`, a przy pozostałych żądaniach brak kolekcji jest awarią, o której
    wołający ma się dowiedzieć."""
    client = _client(always(status=404, text="Not found"))

    with pytest.raises(DbQdrantError, match="404"):
        await client.request("POST", f"{PATH}/points/count", json={"exact": True})


# --- get_or_none --------------------------------------------------------------------------

async def test_missing_resource_reads_as_none() -> None:
    """Sprawdza, czy odczyt `get_or_none()` oddaje `None`, gdy Qdrant odpowiada statusem 404, czyli
    gdy pytanego zasobu nie ma.

    Wyłapuje odczyt, który brak kolekcji zgłasza jako błąd: to zwykły stan początkowy, a nie awaria,
    i od niego zaczyna się zakładanie kolekcji."""
    client = _client(routed({("GET", PATH): httpx.Response(404)}))

    assert await client.get_or_none(PATH) is None


async def test_existing_resource_reads_as_its_body() -> None:
    """Sprawdza, czy odczyt `get_or_none()` przy statusie 200 oddaje treść odpowiedzi jako słownik,
    bez zmian.

    Wyłapuje odczyt, który gubi albo zmienia treść odpowiedzi: z niej kolekcja czyta opis
    istniejącej kolekcji i sprawdza jej wektory."""
    client = _client(routed({("GET", PATH): httpx.Response(200, json={"result": {"a": 1}})}))

    assert await client.get_or_none(PATH) == {"result": {"a": 1}}


async def test_failed_read_is_an_error_not_a_missing_resource() -> None:
    """Sprawdza, czy odczyt `get_or_none()` przy statusie 500 kończy się błędem `DbQdrantError`
    z numerem statusu, zamiast oddać `None`.

    Wyłapuje odczyt, który każdą nieudaną odpowiedź czyta jako „nie ma": awaria Qdranta wyglądałaby
    wtedy jak brak kolekcji i wołający zakładałby ją od nowa."""
    client = _client(routed({("GET", PATH): httpx.Response(500, text="boom")}))

    with pytest.raises(DbQdrantError, match="500"):
        await client.get_or_none(PATH)


# --- awarie transportu --------------------------------------------------------------------

async def test_unreachable_qdrant_becomes_our_error() -> None:
    """Sprawdza, czy odmowa połączenia z Qdrantem kończy się naszym błędem `DbQdrantError`, zarówno
    w `request()`, jak i w `get_or_none()`.

    Wyłapuje wyjątek biblioteki `httpx` wydostający się z klienta: kod korzystający z klienta łapie
    tylko nasz błąd, więc niedostępny Qdrant kończyłby się nieobsłużonym wyjątkiem."""
    client = _client(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(DbQdrantError):
        await client.request("GET", PATH)

    with pytest.raises(DbQdrantError):
        await client.get_or_none(PATH)


async def test_timeout_names_the_request() -> None:
    """Sprawdza, czy brak odpowiedzi Qdranta w wyznaczonym czasie kończy się błędem `DbQdrantError`,
    który podaje metodę i ścieżkę żądania, tutaj „GET /collections/tickets".

    Wyłapuje komunikat o przekroczeniu czasu bez wskazania żądania: ścieżka zawiera nazwę kolekcji,
    więc bez niej nie byłoby wiadomo, przy której operacji i kolekcji Qdrant zamilkł."""
    client = _client(raising(httpx.TimeoutException("timed out")))

    with pytest.raises(DbQdrantError, match=f"GET {PATH}"):
        await client.get_or_none(PATH)


async def test_non_json_body_becomes_our_error() -> None:
    """Sprawdza, czy odpowiedź ze statusem 200, której treść nie jest JSON-em (tutaj „<html>", jak
    strona błędu serwera pośredniczącego), kończy się błędem `DbQdrantError` mówiącym o JSON-ie.

    Wyłapuje klienta, który wypuszcza surowy błąd dekodowania: awaria wyszłaby wtedy daleko od
    przyczyny i nie mówiłaby, że zawiodła odpowiedź Qdranta."""
    client = _client(always(text="<html>"))

    with pytest.raises(DbQdrantError, match="JSON"):
        await client.request("GET", PATH)


async def test_json_that_is_not_an_object_becomes_our_error() -> None:
    """Sprawdza, czy odpowiedź ze statusem 200, która jest poprawnym JSON-em, ale listą zamiast
    obiektu, kończy się błędem `DbQdrantError` nazywającym otrzymany typ (`list`).

    Wyłapuje klienta, który oddaje taką odpowiedź dalej: wołający czytają ją jak słownik, więc
    pomyłka wyszłaby u nich jako niejasny błąd typu."""
    client = _client(routed({("GET", PATH): httpx.Response(200, json=[1, 2])}))

    with pytest.raises(DbQdrantError, match="list"):
        await client.request("GET", PATH)


# --- zamknięcie ---------------------------------------------------------------------------

async def test_aclose_closes_the_connections_and_may_be_repeated() -> None:
    """Sprawdza, czy `aclose()` zamyka połączenia klienta i czy drugie wywołanie przechodzi bez
    błędu.

    Wyłapuje zamknięcie, które zostawia otwarte połączenia albo pada przy powtórzeniu: jednego
    klienta zamyka każda kolekcja, która na nim stoi, więc bywa zamykany kilka razy."""
    client = _client(always())

    await client.aclose()
    await client.aclose()

    assert client._client.is_closed
