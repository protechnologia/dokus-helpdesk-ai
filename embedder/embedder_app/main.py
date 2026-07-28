import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from embedder_app.config import get_settings
from embedder_app.encoding import get_encoder
from embedder_app.errors import REQUEST_ID_HEADER, register_exception_handlers
from embedder_app.routers import embed, health

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
    Assembles the embedder: configuration, logging, encoder, middleware, exception handlers,
    routers. A factory rather than a module-level singleton, so tests build an isolated instance
    instead of inheriting the state of an app created at import time.

    Example args:
        (none)

    Example result:
        FastAPI instance serving GET /health and POST /embed

    Raises:
        EncoderConfigError: `EMBEDDING_BACKEND` names a backend this build cannot construct
    """
    settings = get_settings()

    _configure_logging(settings.log_level)

    # Built here, not on first request: a misconfigured backend must kill the container at
    # startup, and a real model must load its weights before the first caller waits on them.
    encoder = get_encoder()

    app = FastAPI(
        title   = "dokus-embedder",
        version = "0.1.0",
    )

    # --- correlation id: accepted from `api` when present, generated otherwise ---
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """
        Description:
        Attaches a correlation id to the request and echoes it back in the response header. Here
        it matters more than in a standalone service: one indexing run fans out into thousands of
        calls from `api`, and without a shared id a failure cannot be traced back to its ticket.

        Example args:
            request=Request(scope={...})
            call_next=<downstream ASGI callable>

        Example result:
            Response with the X-Request-ID header set
        """
        # An id from the caller wins: it lets one id span `api` and this service.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        started_at = time.perf_counter()
        response   = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id

        # Identifiers and timings only — never request bodies (they carry ticket text).
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
    app.include_router(embed.router)

    # Announced at startup because a wrong dimension only shows up much later, as a rejected
    # upsert into a collection built for a different vector size.
    logger.info(
        "embedder ready backend=%s model=%s dimension=%d",
        settings.embedding_backend,
        encoder.model_name,
        encoder.dimension,
    )

    return app


app = create_app()
