import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from embedder_app.encoding import EncoderConfigError, EncoderError
from embedder_app.models import ErrorResponse

logger = logging.getLogger(__name__)

# Header used both to accept an upstream correlation id and to return the one we used. The value
# normally comes from `api`, which called us — one id has to span both services or the two log
# streams cannot be stitched together.
REQUEST_ID_HEADER = "X-Request-ID"

# An encoding failure is reported as "temporarily unavailable", not "broken request": by the time
# a request reaches us, configuration has already been validated at startup, so what remains is
# transient (out of memory, backend hiccup). 503 tells an indexing run to back off and retry
# rather than to discard the ticket.
ENCODER_FAILURE_STATUS = 503


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
        exc=HTTPException(status_code=404, detail="Not Found")

    Example result:
        JSONResponse(status_code=404, content={"detail": "Not Found", "request_id": "8f14…"})
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
    Handles `RequestValidationError` — the most common 422 here, because every request that omits
    `mode` or sends an empty batch lands in it. It is NOT an `HTTPException`, so without its own
    handler it would bypass the one above and return FastAPI's raw error shape.

    Example args:
        request=Request(scope={...})
        exc=RequestValidationError(errors=[{"loc": ["body", "mode"], "msg": "Field required"}])

    Example result:
        JSONResponse(status_code=422, content={"detail": "…", "request_id": "8f14…"})
    """
    assert isinstance(exc, RequestValidationError)

    request_id = _request_id_of(request)
    # Full error list at DEBUG only: it echoes submitted values, i.e. ticket text.
    logger.warning(
        "validation_error path=%s error_count=%d request_id=%s",
        request.url.path,
        len(exc.errors()),
        request_id,
    )
    logger.debug("validation_error details=%s", exc.errors())

    body = ErrorResponse(detail="Request validation failed", request_id=request_id)

    return JSONResponse(status_code=422, content=body.model_dump())


async def _handle_encoder_error(request: Request, exc: Exception) -> JSONResponse:
    """
    Description:
    Handles a failure of the encoding layer. Its purpose is containment: whatever a backend
    library raises has already been translated into `EncoderError`, and here it stops becoming
    a bare 500 with a stack-shaped body. The message is deliberately generic — a model library's
    exception text may quote the input, which is customer data.

    Example args:
        request=Request(scope={...})
        exc=EncoderError("CUDA out of memory")

    Example result:
        JSONResponse(status_code=503, content={"detail": "Encoding failed", "request_id": "8f14…"})

    Raises:
        EncoderConfigError: re-raised untouched — see below
    """
    # EncoderConfigError is a SUBCLASS of EncoderError, so it would land here silently. It must
    # not: a configuration error means the process should never have started serving, and today
    # it cannot occur mid-request only because `get_encoder()` runs at startup. If that ever
    # changes, this re-raise keeps the failure loud instead of turning it into a polite 503.
    if isinstance(exc, EncoderConfigError):
        raise exc

    assert isinstance(exc, EncoderError)

    request_id = _request_id_of(request)
    # Exception message at ERROR because it is ours (no user text), unlike the request body.
    logger.error(
        "encoder_error path=%s error=%s request_id=%s",
        request.url.path,
        exc,
        request_id,
    )

    body = ErrorResponse(detail="Encoding failed", request_id=request_id)

    return JSONResponse(status_code=ENCODER_FAILURE_STATUS, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    """
    Description:
    Registers every exception handler on the application. Kept separate from app assembly so a
    unit test can attach the handlers to a bare app and exercise them without the real routes.

    Example args:
        app=FastAPI()

    Example result:
        None — the app answers with the ErrorResponse shape for every handled failure kind
    """
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(EncoderError, _handle_encoder_error)
