import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.anonymization import AnonymizationConfigError, AnonymizationError
from app.errors import register_exception_handlers
from app.llm import LLMConfigError, LLMError


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Buduje nagą aplikację z samymi handlerami i trasami, które prowokują błąd. Prawdziwa aplikacja
    uzależniłaby te asercje od tego, jakie endpointy akurat istnieją.

    Example args:
        (wstrzykiwane przez pytest)

    Example result:
        TestClient nad aplikacją z /boom, /needs-param, /llm-down, /llm-misconfigured,
        /anonymization-down i /anonymization-misconfigured
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

    # raise_server_exceptions=False: odpowiadają handlery, zamiast wyjątku wpadającego do testu.
    return TestClient(app, raise_server_exceptions=False)


def test_http_exception_uses_uniform_shape(client: TestClient) -> None:
    """HTTPException → zadeklarowany status i kształt ErrorResponse."""
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"
    assert "request_id" in response.json()


def test_validation_error_returns_422_in_same_shape(client: TestClient) -> None:
    """Brak parametru → 422 w kształcie ErrorResponse, nie surowa lista błędów FastAPI."""
    response = client.get("/needs-param")

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_validation_error_hides_submitted_values(client: TestClient) -> None:
    """Zła wartość parametru → treść odpowiedzi jej nie cytuje (może to być dana klienta)."""
    response = client.get("/needs-param", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert "not-a-number" not in response.text


@pytest.mark.parametrize(
    "path, detail",
    [
        ("/llm-down",           "Language model call failed"),
        ("/anonymization-down", "Anonymization failed"),
    ],
    ids=["llm", "anonymization"],
)
def test_a_dependency_failure_becomes_service_unavailable(
    client: TestClient,
    path:   str,
    detail: str,
) -> None:
    """Awaria modelu albo anonimizatora w trakcie żądania → 503: wołający ponawia albo decyduje
    sam, zamiast winić własne wejście."""
    response = client.get(path)

    assert response.status_code     == 503
    assert response.json()["detail"] == detail


@pytest.mark.parametrize("path", ["/llm-down", "/anonymization-down"], ids=["llm", "anonymization"])
def test_a_dependency_failure_hides_its_message(client: TestClient, path: str) -> None:
    """Treść wyjątku zależności → nigdy w odpowiedzi: może cytować prompt albo dane klienta."""
    response = client.get(path)

    assert "Drukarka" not in response.text
    assert "Kowalski" not in response.text


@pytest.mark.parametrize(
    "path",
    ["/llm-misconfigured", "/anonymization-misconfigured"],
    ids=["llm", "anonymization"],
)
def test_config_error_is_not_dressed_up_as_a_transient_failure(
    client: TestClient,
    path:   str,
) -> None:
    """Błąd konfiguracji (podklasa błędu zależności) → NIE 503; zła konfiguracja ma być głośna."""
    response = client.get(path)

    assert response.status_code == 500


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Handler poza middleware → request_id to None, nie wywrotka."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
