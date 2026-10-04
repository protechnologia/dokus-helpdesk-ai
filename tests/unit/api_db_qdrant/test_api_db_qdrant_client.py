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
    """QDRANT_URL="" (tak compose podstawia brak zmiennej) → błąd przy budowie, a nie błąd
    połączenia w środku przebiegu."""
    with pytest.raises(DbQdrantConfigError, match="QDRANT_URL"):
        QdrantClient(base_url=blank)


# --- request ------------------------------------------------------------------------------

async def test_request_sends_what_it_was_given_and_returns_the_body() -> None:
    """Metoda, ścieżka, parametry i treść → idą na drut bez zmian, a odpowiedź wraca jako
    słownik."""
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
    """Qdrant odrzuca żądanie → błąd niesie jego wyjaśnienie: to jedyne miejsce, które mówi
    DLACZEGO."""
    client = _client(always(status=400, text="Wrong input: Vector dimension error"))

    with pytest.raises(DbQdrantError, match="Vector dimension error"):
        await client.request("PUT", f"{PATH}/points", json={"points": []})


async def test_missing_resource_is_an_error_for_request() -> None:
    """404 przy zwykłym żądaniu → błąd; tylko `get_or_none()` czyta brak jako odpowiedź."""
    client = _client(always(status=404, text="Not found"))

    with pytest.raises(DbQdrantError, match="404"):
        await client.request("POST", f"{PATH}/points/count", json={"exact": True})


# --- get_or_none --------------------------------------------------------------------------

async def test_missing_resource_reads_as_none() -> None:
    """404 przy odczycie → None: brak kolekcji to zwykły stan początkowy, nie awaria."""
    client = _client(routed({("GET", PATH): httpx.Response(404)}))

    assert await client.get_or_none(PATH) is None


async def test_existing_resource_reads_as_its_body() -> None:
    """200 przy odczycie → treść odpowiedzi jako słownik."""
    client = _client(routed({("GET", PATH): httpx.Response(200, json={"result": {"a": 1}})}))

    assert await client.get_or_none(PATH) == {"result": {"a": 1}}


async def test_failed_read_is_an_error_not_a_missing_resource() -> None:
    """500 przy odczycie → błąd, nie None: padnięty Qdrant nie może wyglądać jak brak kolekcji,
    bo wołający założyłby ją od nowa."""
    client = _client(routed({("GET", PATH): httpx.Response(500, text="boom")}))

    with pytest.raises(DbQdrantError, match="500"):
        await client.get_or_none(PATH)


# --- awarie transportu --------------------------------------------------------------------

async def test_unreachable_qdrant_becomes_our_error() -> None:
    """Odmowa połączenia → `DbQdrantError`, nigdy typ `httpx`: transport nie wychodzi do domeny
    (zasada 4)."""
    client = _client(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(DbQdrantError):
        await client.request("GET", PATH)

    with pytest.raises(DbQdrantError):
        await client.get_or_none(PATH)


async def test_timeout_names_the_request() -> None:
    """Qdrant nie odpowiada w czasie → błąd nazywa metodę i ścieżkę, czyli także kolekcję."""
    client = _client(raising(httpx.TimeoutException("timed out")))

    with pytest.raises(DbQdrantError, match=f"GET {PATH}"):
        await client.get_or_none(PATH)


async def test_non_json_body_becomes_our_error() -> None:
    """200 z treścią spoza JSON-a (zwykle strona błędu proxy) → `DbQdrantError`, a nie awaria
    dekodowania daleko od przyczyny."""
    client = _client(always(text="<html>"))

    with pytest.raises(DbQdrantError, match="JSON"):
        await client.request("GET", PATH)


async def test_json_that_is_not_an_object_becomes_our_error() -> None:
    """200 z listą zamiast obiektu → `DbQdrantError`: wołający czytają odpowiedź jak słownik."""
    client = _client(routed({("GET", PATH): httpx.Response(200, json=[1, 2])}))

    with pytest.raises(DbQdrantError, match="list"):
        await client.request("GET", PATH)


# --- zamknięcie ---------------------------------------------------------------------------

async def test_aclose_closes_the_connections_and_may_be_repeated() -> None:
    """`aclose()` → zamknięte połączenia; drugie wywołanie nic nie robi, bo jednego klienta
    zamyka każda kolekcja, która na nim stoi."""
    client = _client(always())

    await client.aclose()
    await client.aclose()

    assert client._client.is_closed
