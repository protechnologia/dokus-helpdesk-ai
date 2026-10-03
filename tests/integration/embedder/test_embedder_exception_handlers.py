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
    """Raised HTTPException → declared status and the ErrorResponse shape."""
    response = client.get("/boom")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
    assert "request_id" in response.json()


def test_validation_error_returns_422_in_same_shape(client: TestClient) -> None:
    """Missing query param → 422 in ErrorResponse shape, not FastAPI's raw error list."""
    response = client.get("/needs-param")

    assert response.status_code == 422
    assert response.json()["detail"] == "Request validation failed"


def test_validation_error_hides_submitted_values(client: TestClient) -> None:
    """Bad query value → response body must not echo the submitted value (it may be ticket text)."""
    response = client.get("/needs-param", params={"limit": "not-a-number"})

    assert response.status_code == 422
    assert "not-a-number" not in response.text


def test_encoder_error_becomes_service_unavailable(client: TestClient) -> None:
    """EncoderError during a request → 503, so an indexing run backs off instead of dropping."""
    response = client.get("/encoder-down")

    assert response.status_code == 503
    assert response.json()["detail"] == "Encoding failed"


def test_encoder_error_body_hides_the_backend_message(client: TestClient) -> None:
    """Backend exception text → never in the body (it may quote the submitted ticket text)."""
    response = client.get("/encoder-down")

    assert "CUDA" not in response.text
    assert "Drukarka" not in response.text


def test_config_error_is_not_dressed_up_as_a_transient_failure(client: TestClient) -> None:
    """EncoderConfigError (an EncoderError subclass) → NOT 503; misconfiguration must stay loud."""
    response = client.get("/encoder-misconfigured")

    assert response.status_code == 500


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Handlers running outside the middleware → request_id is None, not a crash."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
