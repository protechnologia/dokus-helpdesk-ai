import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import register_exception_handlers
from app.llm import LLMConfigError, LLMError


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Builds a bare app with only the handlers under test plus two provoking routes. Using the real
    application would tie these assertions to whatever endpoints exist at the time.

    Example args:
        (injected by pytest)

    Example result:
        TestClient over an app exposing /boom, /needs-param, /llm-down and /llm-misconfigured
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

    # raise_server_exceptions=False: let the handlers answer instead of re-raising into the test.
    return TestClient(app, raise_server_exceptions=False)


def test_http_exception_uses_uniform_shape(client: TestClient) -> None:
    """Raised HTTPException → declared status and the ErrorResponse shape."""
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket not found"
    assert "request_id" in response.json()


def test_validation_error_returns_422_in_same_shape(client: TestClient) -> None:
    """Missing query param → 422 in ErrorResponse shape, not FastAPI's raw error list."""
    response = client.get("/needs-param")

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_validation_error_hides_submitted_values(client: TestClient) -> None:
    """Bad query value → response body must not echo the submitted value (it may be user data)."""
    response = client.get("/needs-param", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert "not-a-number" not in response.text


def test_llm_error_becomes_service_unavailable(client: TestClient) -> None:
    """LLMError during a request → 503, so the caller retries instead of blaming its own input."""
    response = client.get("/llm-down")

    assert response.status_code == 503
    assert response.json()["detail"] == "Language model call failed"


def test_llm_error_body_hides_the_provider_message(client: TestClient) -> None:
    """Provider exception text → never in the body (it may quote the prompt, i.e. ticket text)."""
    response = client.get("/llm-down")

    assert "timed out" not in response.text
    assert "Drukarka" not in response.text


def test_config_error_is_not_dressed_up_as_a_transient_failure(client: TestClient) -> None:
    """LLMConfigError (an LLMError subclass) → NOT 503; misconfiguration must stay loud."""
    response = client.get("/llm-misconfigured")

    assert response.status_code == 500


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Handlers running outside the middleware → request_id is None, not a crash."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
