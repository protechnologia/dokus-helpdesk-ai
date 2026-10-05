import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.agent_graphs.factory import close_process_agent_tools
from app.config import Settings
from app.entry_routers.gate.router import router as gate_router
from app.entry_routers.health.router import router as health_router
from app.entry_routers.parse_ticket.router import router as parse_ticket_router
from app.entry_routers.polish.router import router as polish_router
from app.entry_routers.search.router import router as search_router
from app.entry_routers.suggest.router import router as suggest_router
from app.errors import REQUEST_ID_HEADER, register_exception_handlers

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


@asynccontextmanager
async def _lifespan(
    app: FastAPI,  # aplikacja, której cykl życia obsługujemy; wymagane przez FastAPI
) -> AsyncIterator[None]:
    """
    Description:
    Cykl życia aplikacji. Przy starcie nic nie robi — klienci powstają przy pierwszym żądaniu,
    które ich potrzebuje. Przy wyłączaniu zamyka narzędzia agenta zbudowane na prawdziwych
    bazach, czyli pulę połączeń Postgresa i połączenia HTTP do embeddera i Qdranta.

    Example args:
        app=FastAPI()

    Example result:
        None — po wyjściu z bloku połączenia narzędzi są zamknięte
    """
    yield

    await close_process_agent_tools()


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
        title    = "dokus-helpdesk-ai",
        version  = "0.1.0",
        lifespan = _lifespan,
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

    for router in (
        health_router,        # /health
        search_router,        # /search
        gate_router,          # /gate/close, /gate/reply
        parse_ticket_router,  # /parse-ticket
        suggest_router,       # /suggest, /variants
        polish_router,        # /polish
    ):
        app.include_router(router)

    return app


app = create_app()
