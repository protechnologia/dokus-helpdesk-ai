import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.db_postgres import DbPostgresConfigError, DbPostgresError
from app.db_qdrant import DbQdrantConfigError, DbQdrantError
from app.engine_anonymization import AnonymizationConfigError, AnonymizationError
from app.engine_embedding import EmbeddingConfigError, EmbeddingError
from app.engine_llm import LLMConfigError, LLMError
from app.errors import register_exception_handlers

# Trasy, które prowokują awarię zależności, i opis, jaki wołający ma wtedy dostać.
DOWN = {
    "/llm-down":           "Language model call failed",
    "/anonymization-down": "Anonymization failed",
    "/embedder-down":      "Embedding service call failed",
    "/qdrant-down":        "Vector index call failed",
    "/postgres-down":      "Text index call failed",
}

# Trasy, które prowokują błąd konfiguracji tych samych zależności.
MISCONFIGURED = [
    "/llm-misconfigured",
    "/anonymization-misconfigured",
    "/embedder-misconfigured",
    "/qdrant-misconfigured",
    "/postgres-misconfigured",
]


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Buduje nagą aplikację z samymi handlerami i trasami, które prowokują błąd. Prawdziwa aplikacja
    uzależniłaby te asercje od tego, jakie endpointy akurat istnieją.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        TestClient nad aplikacją z /boom, /needs-param oraz trasami z `DOWN` i `MISCONFIGURED`
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    @app.get("/needs-param")
    async def needs_param(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @app.get("/llm-down")
    async def llm_down() -> None:
        raise LLMError("Read timed out; prompt was 'Drukarka nie drukuje'")

    @app.get("/llm-misconfigured")
    async def llm_misconfigured() -> None:
        raise LLMConfigError("Unknown LLM_PROVIDER='openai'")

    @app.get("/anonymization-down")
    async def anonymization_down() -> None:
        raise AnonymizationError("nie rozpoznano: 'Jan Kowalski, ul. Polna 3'")

    @app.get("/anonymization-misconfigured")
    async def anonymization_misconfigured() -> None:
        raise AnonymizationConfigError("atrapa anonimizatora przy LLM_PROVIDER=ollama")

    @app.get("/embedder-down")
    async def embedder_down() -> None:
        raise EmbeddingError("Could not reach the embedder; text was 'Drukarka nie drukuje'")

    @app.get("/embedder-misconfigured")
    async def embedder_misconfigured() -> None:
        raise EmbeddingConfigError("EMBEDDING_BASE_URL nie może być puste")

    @app.get("/qdrant-down")
    async def qdrant_down() -> None:
        raise DbQdrantError("Qdrant odpowiedział HTTP 500: payload 'Jan Kowalski'")

    @app.get("/qdrant-misconfigured")
    async def qdrant_misconfigured() -> None:
        raise DbQdrantConfigError("punkt 'df3b' nie ma `ticket_id` w payloadzie")

    @app.get("/postgres-down")
    async def postgres_down() -> None:
        raise DbPostgresError("zapytanie do Postgresa nie powiodło się: 'Jan Kowalski'")

    @app.get("/postgres-misconfigured")
    async def postgres_misconfigured() -> None:
        raise DbPostgresConfigError("POSTGRES_PASSWORD nie może być puste")

    # raise_server_exceptions=False: odpowiadają handlery, zamiast wyjątku wpadającego do testu.
    return TestClient(app, raise_server_exceptions=False)


def test_http_exception_uses_uniform_shape(client: TestClient) -> None:
    """Sprawdza, czy błąd zgłoszony przez trasę (`HTTPException` ze statusem 404) wraca do
    wołającego z tym samym statusem i we wspólnym kształcie błędu: z opisem w polu `detail`
    i z polem `request_id`.

    Wyłapuje obsługę błędów, która zmienia status albo oddaje błąd w innym kształcie: wołający
    musiałby wtedy obsługiwać kilka różnych postaci błędu."""
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"
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

    Wyłapuje odpowiedź, która cytuje wejście: przysłana wartość może być daną klienta, więc nie
    powinna wracać w komunikacie błędu."""
    response = client.get("/needs-param", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert "not-a-number" not in response.text


@pytest.mark.parametrize("path, detail", DOWN.items(), ids=lambda value: value.strip("/"))
def test_a_dependency_failure_becomes_service_unavailable(
    client: TestClient,
    path:   str,
    detail: str,
) -> None:
    """Sprawdza, czy awaria zależności w trakcie żądania — modelu językowego, anonimizatora,
    embeddera, Qdranta albo Postgresa — wraca jako status 503 z ogólnym opisem, osobnym dla każdej
    z nich.

    Wyłapuje awarię zależności oddaną jako zwykły błąd serwera: taki błąd nie mówi wołającemu,
    czy zawiniło jego żądanie, czy usługa chwilowo nie działa i można ponowić albo zdecydować
    samemu."""
    response = client.get(path)

    assert response.status_code     == 503
    assert response.json()["detail"] == detail


@pytest.mark.parametrize("path", DOWN, ids=lambda value: value.strip("/"))
def test_a_dependency_failure_hides_its_message(client: TestClient, path: str) -> None:
    """Sprawdza, czy odpowiedź po awarii którejkolwiek zależności nie zawiera treści wyjątku:
    w teście wyjątki cytują fragment zgłoszenia i zmyślone nazwisko, a w odpowiedzi nie ma
    żadnego z nich.

    Wyłapuje przeciek danych klienta przez komunikat błędu: wyjątek zależności potrafi zacytować
    prompt, tekst zgłoszenia albo fragment odpowiedzi bazy."""
    response = client.get(path)

    assert "Drukarka" not in response.text
    assert "Kowalski" not in response.text


@pytest.mark.parametrize("path", MISCONFIGURED, ids=lambda value: value.strip("/"))
def test_config_error_is_not_dressed_up_as_a_transient_failure(
    client: TestClient,
    path:   str,
) -> None:
    """Sprawdza, czy błąd konfiguracji którejkolwiek zależności kończy żądanie statusem 500, a nie
    503, choć w kodzie jest odmianą błędu zależności, który daje 503.

    Wyłapuje złą konfigurację przebraną za chwilową awarię: status 503 znaczy „spróbuj za
    chwilę", a przy błędnej konfiguracji czekanie nic nie da, więc usterka ma być widoczna od
    razu."""
    response = client.get(path)

    assert response.status_code == 500


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Sprawdza, czy obsługa błędu działa także w aplikacji bez warstwy nadającej identyfikator
    żądania: odpowiedź wraca normalnie, a pole `request_id` jest puste.

    Wyłapuje obsługę błędu, która zakłada, że identyfikator zawsze jest, i sama się wywraca:
    zamiast opisu właściwego błędu wołający dostałby wtedy błąd obsługi błędu."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
