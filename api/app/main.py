import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.config import Settings
from app.errors import REQUEST_ID_HEADER, register_exception_handlers
from app.routers import gate, health, parse_ticket, polish, search, suggest

logger = logging.getLogger(__name__)


def _configure_logging(
    level: str,  # np. "DEBUG"
) -> None:
    """
    Description:
    Ustawia logowanie raz, przy montażu. `force=True` podmienia handlery zainstalowane przez
    uvicorna, żeby nasze wpisy nie wychodziły dwa razy w dwóch formatach.

    Example args:
        level="INFO"

    Example result:
        None — logowanie skonfigurowane dla całego procesu
    """
    logging.basicConfig(
        level   = level.upper(),
        format  = "%(asctime)s %(levelname)s %(name)s %(message)s",
        force   = True,
    )


def create_app() -> FastAPI:
    """
    Description:
    Składa aplikację: konfiguracja, logowanie, middleware, handlery wyjątków, routery. Fabryka,
    a nie singleton modułu, żeby testy budowały własną instancję zamiast dziedziczyć stan
    aplikacji utworzonej przy imporcie.

    Example args:
        (brak)

    Example result:
        FastAPI z /health, /search, /gate/close, /gate/reply, /parse-ticket, /suggest, /variants
        i /polish
    """
    settings = Settings()

    _configure_logging(settings.log_level)

    app = FastAPI(
        title   = "dokus-helpdesk-ai",
        version = "0.1.0",
    )

    # --- identyfikator korelacji: przyjęty od wołającego, jeśli jest, inaczej nadany ---
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """
        Description:
        Dokleja do żądania identyfikator korelacji i odsyła go w nagłówku odpowiedzi, żeby dało
        się zszyć wszystkie wpisy logu jednego żądania. To korelacja logów, NIE monitoring — nic
        nie mierzy i o niczym nie decyduje.

        Example args:
            request=Request(scope={...})
            call_next=<wywołanie ASGI dalej w łańcuchu>

        Example result:
            Response z ustawionym nagłówkiem X-Request-ID
        """
        # Identyfikator od wołającego wygrywa: dzięki temu jeden id spina kilka usług.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        started_at = time.perf_counter()
        response   = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id

        # Tylko identyfikatory i czasy — nigdy treść żądania (niesie dane klienta).
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

    for module in (health, search, gate, parse_ticket, suggest, polish):
        app.include_router(module.router)

    return app


app = create_app()
