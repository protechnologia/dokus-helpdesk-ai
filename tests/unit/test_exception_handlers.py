import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.errors import register_exception_handlers


@pytest.fixture
def client() -> TestClient:
    """
    Description:
    Builds a bare app with only the handlers under test plus two provoking routes. Using the real
    application would tie these assertions to whatever endpoints exist at the time.

    Example args:
        (injected by pytest)

    Example result:
        TestClient over an app exposing /boom and /needs-param
    """
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    @app.get("/needs-param")
    async def needs_param(limit: int) -> dict[str, int]:
        return {"limit": limit}

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


def test_request_id_is_absent_without_middleware(client: TestClient) -> None:
    """Handlers running outside the middleware → request_id is None, not a crash."""
    response = client.get("/boom")

    assert response.json()["request_id"] is None
