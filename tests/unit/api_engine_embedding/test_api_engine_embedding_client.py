import httpx
import pytest

from app.engine_embedding import EmbeddingClient, EmbeddingConfigError, EmbeddingError
from tests.helpers_transport import always, capturing, raising, with_transport

BASE_URL = "http://embedder:8000"

# One vector wide enough to be recognisable in assertions, narrow enough to write out.
VECTOR = [0.1, -0.2, 0.3]

# The single answer this client's happy path needs. Passed explicitly rather than defaulted to,
# because the shape is this service's contract, not a shared one.
ONE_VECTOR = {"vectors": [VECTOR]}

# What the embedder answers while a test inspects the REQUEST. This client speaks to one route, so
# the map is a constant instead of a per-test literal (`routed()`'s permissive default would work
# too, but it answers with Qdrant's shape, which would make an assertion here read as an accident).
EMBED_ROUTE = {("POST", "/embed"): httpx.Response(200, json=ONE_VECTOR)}


def _client(handler: httpx.MockTransport) -> EmbeddingClient:
    """
    Description:
    Builds an embedder client answering from a handler instead of a socket. Only the construction
    is local — the rigging itself lives in `with_transport()`, together with the reasoning for
    replacing a private attribute.

    Example args:
        handler=always({"vectors": [[0.1, -0.2, 0.3]]})

    Example result:
        EmbeddingClient answering from the handler
    """
    return with_transport(EmbeddingClient(base_url=BASE_URL), handler)


def test_empty_base_url_is_refused_at_build_time() -> None:
    """Sprawdza, czy klient embeddera budowany z pustym adresem kończy się błędem konfiguracji,
    który wymienia zmienną `EMBEDDING_BASE_URL`.

    Wyłapuje klienta przyjmującego pusty adres: `docker compose` wstawia pusty tekst za
    nieustawioną zmienną, a błąd wyszedłby dopiero przy pierwszym żądaniu, z niejasnym
    komunikatem."""
    with pytest.raises(EmbeddingConfigError, match="EMBEDDING_BASE_URL"):
        EmbeddingClient(base_url="")


def test_whitespace_base_url_is_refused_at_build_time() -> None:
    """Sprawdza, czy adres embeddera złożony z samych spacji jest traktowany jak brak adresu
    i kończy się błędem konfiguracji przy budowie klienta.

    Wyłapuje kontrolę, która odsiewa tylko dokładnie pusty tekst: klient powstałby z adresem ze
    spacji i padłby dopiero przy pierwszym żądaniu."""
    with pytest.raises(EmbeddingConfigError):
        EmbeddingClient(base_url="   ")


# One test per mode rather than a loop: the point is that each named method is wired to its own
# vector space, and a parametrised failure has to say WHICH method broke without decoding an id.
@pytest.mark.parametrize(
    ("method_name", "expected_mode"),
    [
        ("embed_query",   "query"),    # new tickets asked against the index
        ("embed_passage", "passage"),  # historical tickets being indexed
        ("embed_sts",     "sts"),      # symmetric ticket-to-ticket comparison
    ],
)
async def test_each_method_sends_its_own_mode(method_name: str, expected_mode: str) -> None:
    """Sprawdza, czy każda z trzech metod klienta wysyła do embeddera swój tryb: `embed_query`
    tryb `query`, `embed_passage` tryb `passage`, a `embed_sts` tryb `sts`.

    Wyłapuje metodę podpiętą pod niewłaściwy tryb: wektory nadal wyglądają poprawnie, więc
    później pomyłki nie da się zauważyć, a wyszukiwanie po cichu daje gorsze wyniki."""
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await getattr(client, method_name)(["Brak tonera"])

    assert seen[0]["body"]["mode"] == expected_mode


async def test_texts_are_sent_as_submitted() -> None:
    """Sprawdza, czy teksty docierają do embeddera bez zmian: tekst „Brak tonera" jest w wysłanym
    żądaniu dokładnie w tej postaci.

    Wyłapuje klienta, który sam dokleja coś do tekstu, na przykład przedrostek trybu:
    przedrostki dodaje usługa embeddera, bo zależą od modelu, a nie od klienta."""
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await client.embed_passage(["Brak tonera"])

    assert seen[0]["body"]["texts"] == ["Brak tonera"]


async def test_the_batch_goes_to_the_embed_path() -> None:
    """Sprawdza, czy jedno wywołanie klienta to dokładnie jedno żądanie `POST` pod ścieżkę
    `/embed`.

    Wyłapuje zmianę ścieżki albo metody żądania oraz żądania nadmiarowe: ścieżka jest częścią
    umowy między dwiema usługami, które wydajemy razem, więc klient z inną ścieżką nie
    dogadałby się z embedderem."""
    seen: list = []
    client     = _client(capturing(seen, EMBED_ROUTE))

    await client.embed_passage(["Brak tonera"])

    assert [(call["method"], call["path"]) for call in seen] == [("POST", "/embed")]


async def test_vectors_are_returned_in_submission_order() -> None:
    """Sprawdza, czy dla trzech tekstów klient oddaje trzy wektory w tej samej kolejności,
    w jakiej przyszły w odpowiedzi embeddera.

    Wyłapuje klienta, który przestawia albo gubi wektory: wołający przypisuje je do tekstów po
    kolei, więc zgłoszenie dostałoby wektor innego zgłoszenia."""
    client = _client(always({"vectors": [[1.0], [2.0], [3.0]]}))

    vectors = await client.embed_passage(["a", "b", "c"])

    assert vectors == [[1.0], [2.0], [3.0]]


async def test_vector_count_mismatch_is_an_error() -> None:
    """Sprawdza, czy odpowiedź z jednym wektorem na dwa wysłane teksty kończy się błędem
    `EmbeddingError`, który podaje liczbę otrzymanych wektorów.

    Wyłapuje brak kontroli liczby wektorów: wołający przypisuje wektory do zgłoszeń po kolei,
    więc przy rozjeździe zgłoszenie dostałoby cudzy wektor, a wyszukiwanie dawałoby złe wyniki
    zamiast błędu."""
    client = _client(always(ONE_VECTOR))

    with pytest.raises(EmbeddingError, match="1 vector"):
        await client.embed_passage(["a", "b"])


async def test_missing_vectors_field_is_an_error() -> None:
    """Sprawdza, czy odpowiedź ze statusem 200, w której nie ma pola `vectors`, kończy się błędem
    `EmbeddingError` wymieniającym to pole.

    Wyłapuje klienta, który sięga po pole bez sprawdzenia: wołający dostałby przypadkowy
    wyjątek Pythona, na przykład `KeyError`, zamiast błędu warstwy embeddera."""
    client = _client(always({"model": "fake"}))

    with pytest.raises(EmbeddingError, match="vectors"):
        await client.embed_passage(["a"])


async def test_server_error_becomes_a_layer_error() -> None:
    """Sprawdza, czy odpowiedź embeddera ze statusem 503 kończy się błędem `EmbeddingError`, który
    podaje ten status.

    Wyłapuje wyjątek biblioteki `httpx` wypuszczony do wołającego: reszta kodu ma znać tylko
    błędy warstwy embeddera, a nie biblioteki, którą klient się łączy (zasada 4)."""
    client = _client(always({"detail": "model down"}, status=503))

    with pytest.raises(EmbeddingError, match="503"):
        await client.embed_passage(["a"])


async def test_connection_failure_becomes_a_layer_error() -> None:
    """Sprawdza, czy brak połączenia z embedderem (tu odmowa połączenia) kończy się błędem
    `EmbeddingError`, który mówi, że nie udało się do niego dotrzeć.

    Wyłapuje surowy błąd transportu wypuszczony do wołającego albo komunikat, z którego nie
    wynika, że embedder jest nieosiągalny."""
    client = _client(raising(httpx.ConnectError("connection refused")))

    with pytest.raises(EmbeddingError, match="reach"):
        await client.embed_passage(["a"])


async def test_timeout_becomes_a_layer_error() -> None:
    """Sprawdza, czy przekroczenie czasu oczekiwania na odpowiedź embeddera kończy się błędem
    `EmbeddingError`, który mówi o przekroczeniu czasu.

    Wyłapuje błąd, z którego nie widać, że chodziło o czas: indeksacja nie mogłaby wtedy
    zdecydować, czy ponowić wywołanie."""
    client = _client(raising(httpx.ReadTimeout("too slow")))

    with pytest.raises(EmbeddingError, match="timed out"):
        await client.embed_passage(["a"])


async def test_non_json_body_becomes_a_layer_error() -> None:
    """Sprawdza, czy odpowiedź ze statusem 200, której treścią jest strona HTML zamiast JSON-a
    (tak wygląda strona błędu pośrednika sieciowego), kończy się błędem `EmbeddingError`
    mówiącym, że treść nie jest JSON-em.

    Wyłapuje błąd dekodowania JSON-a wypuszczony do wołającego: z takiego wyjątku nie widać, że
    zawiódł embedder albo coś po drodze do niego."""
    client = _client(always(text="<html>oops</html>"))

    with pytest.raises(EmbeddingError, match="non-JSON"):
        await client.embed_passage(["a"])
