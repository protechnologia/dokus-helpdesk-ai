import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.models import ErrorResponse

logger = logging.getLogger(__name__)

# Header used both to accept an upstream correlation id and to return the one we used.
REQUEST_ID_HEADER = "X-Request-ID"


def _request_id_of(request: Request) -> str | None:   # e.g. Request with state.request_id set
    """
    Description:
    Reads the correlation id the middleware stored on the request. Returns None when the handler
    runs outside that middleware (e.g. a bare app in a unit test), so error handling never fails
    because of a missing id.

    Example args:
        request=Request(scope={...})

    Example result:
        "8f14e45fceea167a5a36dedd4bea2543"
    """
    return getattr(request.state, "request_id", None)


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Description:
    Turns an `HTTPException` into the uniform error payload. The cause is logged HERE, not in
    middleware: middleware sees a finished `Response` whose body no longer explains anything,
    while `detail` — the only "why" — lives on the exception.

    Example args:
        request=Request(scope={...})
        exc=HTTPException(status_code=404, detail="Ticket not found")

    Example result:
        JSONResponse(status_code=404, content={"detail": "Ticket not found", "request_id": "8f14…"})
    """
    # Signature is typed as Exception because FastAPI's handler registry is untyped; narrow here.
    assert isinstance(exc, HTTPException)

    request_id = _request_id_of(request)
    logger.warning(
        "http_error status=%s path=%s detail=%s request_id=%s",
        exc.status_code,
        request.url.path,
        exc.detail,
        request_id,
    )

    body = ErrorResponse(detail=str(exc.detail), request_id=request_id)

    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """
    Description:
    Handles `RequestValidationError` — the most common 422. It is NOT an `HTTPException`, so
    without its own handler it would bypass the one above and return FastAPI's raw error shape,
    breaking the uniform contract.

    Example args:
        request=Request(scope={...})
        exc=RequestValidationError(errors=[{"loc": ["query", "limit"], "msg": "…"}])

    Example result:
        JSONResponse(status_code=422, content={"detail": "…", "request_id": "8f14…"})
    """
    assert isinstance(exc, RequestValidationError)

    request_id = _request_id_of(request)
    # Full error list at DEBUG only: it echoes submitted values, i.e. potentially user data.
    logger.warning(
        "validation_error path=%s error_count=%d request_id=%s",
        request.url.path,
        len(exc.errors()),
        request_id,
    )
    logger.debug("validation_error details=%s", exc.errors())

    body = ErrorResponse(detail="Request validation failed", request_id=request_id)

    return JSONResponse(status_code=422, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """
    Description:
    Registers every exception handler on the application. Kept separate from app assembly so a
    unit test can attach the handlers to a bare app and exercise them without the real routes.

    Example args:
        app=FastAPI()

    Example result:
        None — the app answers with the ErrorResponse shape for both handled failure kinds
    """
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
