import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from embedder_app.encoding import EncoderConfigError, EncoderError
from embedder_app.errors import register_exception_handlers


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Builds a bare app with only the handlers under test plus three provoking routes. Using the
    real application would tie these assertions to whatever endpoints exist at the time.

    Example args:
        (injected by pytest)

    Example result:
        TestClient over an app exposing /boom, /needs-param, /encoder-down and
        /encoder-misconfigured
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/needs-param")
    async def needs_param(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/encoder-down")
    async def encoder_down() -> None:
        raise EncoderError("CUDA out of memory while encoding 'Drukarka nie drukuje'")

    @app.get("/encoder-misconfigured")
    async def encoder_misconfigured() -> None:
        raise EncoderConfigError("Unknown EMBEDDING_BACKEND='poldense'")

    # raise_server_exceptions=False: let the handlers answer instead of re-raising into the test.
    return TestClient(app, raise_server_exceptions=False)


def test_http_exception_uses_uniform_shape(client: TestClient) -> None:
    """Sprawdza, czy błąd zgłoszony przez trasę (`HTTPException` ze statusem 404) wraca do
    wołającego z tym samym statusem i we wspólnym kształcie błędu: z opisem w polu `detail`
    i z polem `request_id`.

    Wyłapuje obsługę błędów, która zmienia status albo oddaje błąd w innym kształcie: wołający
    musiałby wtedy obsługiwać kilka różnych postaci błędu."""
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    assert "request_id" in response.json()


def test_validation_error_returns_422_in_same_shape(client: TestClient) -> None:
    """Sprawdza, czy żądanie bez wymaganego parametru dostaje status 422 we wspólnym kształcie
    błędu, z ogólnym opisem „Request validation failed".

    Wyłapuje brak osobnej obsługi błędów walidacji: FastAPI oddałoby wtedy własną, surową listę
    błędów, w innym kształcie niż pozostałe błędy usługi."""
    response = client.get("/needs-param")

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_validation_error_hides_submitted_values(client: TestClient) -> None:
    """Sprawdza, czy odpowiedź na żądanie z błędną wartością parametru (tekst zamiast liczby) ma
    status 422 i nie powtarza przysłanej wartości.

    Wyłapuje odpowiedź, która cytuje wejście: przysłana wartość może być tekstem zgłoszenia,
    więc nie powinna wracać w komunikacie błędu."""
    response = client.get("/needs-param", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert "not-a-number" not in response.text


def test_encoder_error_becomes_service_unavailable(client: TestClient) -> None:
    """Sprawdza, czy awaria liczenia wektorów w trakcie żądania (`EncoderError`) wraca jako status
    503 z ogólnym opisem „Encoding failed".

    Wyłapuje awarię oddaną jako zwykły błąd serwera: przebieg indeksacji nie wiedziałby wtedy,
    że ma odczekać i ponowić, i porzuciłby zgłoszenie."""
    response = client.get("/encoder-down")

    assert response.status_code == 503
    assert response.json()["detail"] == "Encoding failed"


def test_encoder_error_body_hides_the_backend_message(client: TestClient) -> None:
    """Sprawdza, czy odpowiedź po awarii liczenia wektorów nie zawiera treści wyjątku: w teście
    wyjątek niesie komunikat biblioteki modelu i fragment tekstu wejściowego, a w odpowiedzi nie
    ma żadnego z nich.

    Wyłapuje przeciek danych klienta przez komunikat błędu: wyjątek biblioteki modelu potrafi
    zacytować tekst, który dostała do zakodowania, czyli treść zgłoszenia."""
    response = client.get("/encoder-down")

    assert "CUDA" not in response.text
    assert "Drukarka" not in response.text


def test_config_error_is_not_dressed_up_as_a_transient_failure(client: TestClient) -> None:
    """Sprawdza, czy błąd konfiguracji embeddera (`EncoderConfigError`) kończy żądanie statusem
    500, a nie 503, choć w kodzie jest odmianą błędu `EncoderError`, który daje 503.

    Wyłapuje złą konfigurację przebraną za chwilową awarię: status 503 znaczy „spróbuj za
    chwilę", a przy błędnej konfiguracji czekanie nic nie da, więc usterka ma być widoczna od
    razu."""
    response = client.get("/encoder-misconfigured")

    assert response.status_code == 500


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Sprawdza, czy obsługa błędu działa także w aplikacji bez warstwy nadającej identyfikator
    żądania: odpowiedź wraca normalnie, a pole `request_id` jest puste.

    Wyłapuje obsługę błędu, która zakłada, że identyfikator zawsze jest, i sama się wywraca:
    zamiast opisu właściwego błędu wołający dostałby wtedy błąd obsługi błędu."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
