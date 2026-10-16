import httpx
import pytest

from app.engine_embedding import EmbeddingClient, EmbeddingConfigError, EmbeddingError
from tests._helpers.embedding import EMBEDDING_MODEL, embedder_answer
from tests._helpers.transport import always, capturing, raising, with_transport

BASE_URL = "http://embedder:8000"

# Jeden wektor: dość szeroki, żeby dało się go rozpoznać w asercji, dość wąski, żeby go wypisać.
VECTOR = [0.1, -0.2, 0.3]

# Jedyna odpowiedź, jakiej potrzebuje udana droga tego klienta, w kształcie kontraktu usługi.
ONE_VECTOR = embedder_answer([VECTOR])

# Odpowiedź embeddera, gdy test sprawdza ŻĄDANIE. Klient mówi do jednej ścieżki, więc mapa jest
# stałą; domyślna odpowiedź `routed()` ma kształt Qdranta i asercja wyglądałaby na przypadek.
EMBED_ROUTE = {("POST", "/embed"): httpx.Response(200, json=ONE_VECTOR)}

# Odpowiedzi z wektorami, ale bez poprawnej nazwy modelu, z opisem przypadku w `id`.
WITHOUT_MODEL = [
    pytest.param({"vectors": [VECTOR]}, id="bez pola"),
    pytest.param({"vectors": [VECTOR], "model": ""}, id="pusta nazwa"),
    pytest.param({"vectors": [VECTOR], "model": 768}, id="liczba zamiast nazwy"),
]


def _client(handler: httpx.MockTransport) -> EmbeddingClient:
    """
    Description:
    Buduje klienta embeddera, który odpowiada z atrapy transportu zamiast z gniazda. Tu jest tylko
    budowa — podmiana transportu i jej uzasadnienie leżą w `with_transport()`.

    Example args:
        handler=always({"vectors": [[0.1, -0.2, 0.3]], "model": "model-testowy"})

    Example result:
        EmbeddingClient odpowiadający z atrapy
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


# Przypadek na tryb: każda nazwana metoda ma być wpięta w swoją przestrzeń wektorową, a błąd ma
# od razu mówić, KTÓRA metoda się zepsuła.
@pytest.mark.parametrize(
    ("method_name", "expected_mode"),
    [
        ("embed_query",   "query"),    # nowe zgłoszenie jako pytanie do indeksu
        ("embed_passage", "passage"),  # historyczne zgłoszenia przy indeksacji
        ("embed_sts",     "sts"),      # porównanie symetryczne, zgłoszenie ze zgłoszeniem
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


async def test_vectors_are_returned_in_submission_order_with_the_model() -> None:
    """Sprawdza, czy dla trzech tekstów klient oddaje trzy wektory w tej samej kolejności,
    w jakiej przyszły w odpowiedzi embeddera, razem z nazwą modelu z odpowiedzi.

    Wyłapuje klienta, który przestawia albo gubi wektory — wołający przypisuje je do tekstów po
    kolei, więc zgłoszenie dostałoby wektor innego zgłoszenia — oraz klienta, który gubi nazwę
    modelu, po której Qdrant odmawia mieszania wektorów dwóch modeli."""
    client = _client(always(embedder_answer([[1.0], [2.0], [3.0]])))

    embedded = await client.embed_passage(["a", "b", "c"])

    assert embedded.vectors == [[1.0], [2.0], [3.0]]
    assert embedded.model   == EMBEDDING_MODEL


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


@pytest.mark.parametrize("answer", WITHOUT_MODEL)
async def test_an_answer_without_the_model_is_an_error(answer: dict) -> None:
    """Sprawdza, czy odpowiedź ze statusem 200 i z wektorami, ale bez nazwy modelu — bez pola,
    z pustą nazwą albo z liczbą zamiast nazwy — kończy się błędem `EmbeddingError` wymieniającym
    pole `model`.

    Wyłapuje klienta, który oddaje wektory bez nazwy modelu: kolekcja nie mogłaby wtedy sprawdzić,
    czy wektory pasują do punktów policzonych innym modelem o tym samym wymiarze."""
    client = _client(always(answer))

    with pytest.raises(EmbeddingError, match="model"):
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
