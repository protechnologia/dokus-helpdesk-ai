import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.config import Settings
from app.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.routers import health

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:                 # e.g. "DEBUG"
    """
    Description:
    Sets up root logging once, at assembly time. `force=True` replaces handlers installed by
    uvicorn, so our records are not emitted twice with two different formats.

    Example args:
        level="INFO"

    Example result:
        None — logging is configured process-wide
    """
    logging.basicConfig(
        level   = level.upper(),
        format  = "%(asctime)s %(levelname)s %(name)s %(message)s",
        force   = True,
    )


def create_app() -> FastAPI:
    """
    Description:
    Assembles the application: configuration, logging, middleware, exception handlers, routers.
    A factory rather than a module-level singleton, so tests build an isolated instance instead
    of inheriting the state of an app created at import time.

    Example args:
        (none)

    Example result:
        FastAPI instance serving GET /health
    """
    settings = Settings()

    _configure_logging(settings.log_level)

    app = FastAPI(
        title   = "dokus-helpdesk-ai",
        version = "0.1.0",
    )

    # --- correlation id: accepted from upstream when present, generated otherwise ---
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """
        Description:
        Attaches a correlation id to the request and echoes it back in the response header, so
        every log line of one request can be stitched together. This is log correlation, NOT
        monitoring — it measures nothing and decides nothing.

        Example args:
            request=Request(scope={...})
            call_next=<downstream ASGI callable>

        Example result:
            Response with the X-Request-ID header set
        """
        # An id from the caller wins: it lets one id span several services.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        started_at = time.perf_counter()
        response   = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id

        # Identifiers and timings only — never request bodies (they carry customer data).
        logger.info(
            "request method=%s path=%s status=%d duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response

    register_exception_handlers(app)
    app.include_router(health.router)

    return app


app = create_app()
