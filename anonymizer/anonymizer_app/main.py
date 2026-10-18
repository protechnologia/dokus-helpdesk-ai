"""
Description:
Usługa `anonymizer`: zamienia dane osobowe w tekście zgłoszenia na znaczniki, zanim `api` wyśle
go do modelu zewnętrznego. Jedyna usługa poza `api`, która widzi surowe zgłoszenie, więc do
logów nie trafia z niego nic poza długością (CLAUDE.md -> „Plan", p. 19).

| trasa             | co robi                                                  |
|-------------------|----------------------------------------------------------|
| `GET /health`     | sonda życia, bez konfiguracji                            |
| `POST /anonymize` | tekst ze znacznikami i nazwa silnika, który go wytworzył |

O czym pamiętać przy zmianach:

- Usługa nie dzieli kodu z `api` ani z `embedder`: middleware, handlery i walidator konfiguracji
  są tu powielone świadomie, a wspólny jest tylko kontrakt HTTP i nazwy zmiennych ENV.
- Nazwa silnika w odpowiedzi to część kontraktu: po niej `api` odmawia wyniku atrapy.
"""

import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from anonymizer_app.config import get_settings
from anonymizer_app.engine import get_engine
from anonymizer_app.errors.handlers import REQUEST_ID_HEADER, register_exception_handlers
from anonymizer_app.routers import anonymize, health

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:  # np. "DEBUG"
    """
    Description:
    Ustawia logowanie raz, przy składaniu aplikacji. `force=True` zastępuje handlery uvicorna,
    żeby wpisy nie wychodziły dwa razy w dwóch formatach.

    Example args:
        level="INFO"

    Example result:
        None — logowanie ustawione dla całego procesu
    """
    logging.basicConfig(
        level  = level.upper(),
        format = "%(asctime)s %(levelname)s %(name)s %(message)s",
        force  = True,
    )


def create_app() -> FastAPI:
    """
    Description:
    Składa usługę: konfiguracja, logowanie, silnik, middleware, handlery wyjątków, trasy. Fabryka,
    a nie singleton modułu, żeby testy budowały własną instancję.

    Example args:
        (brak)

    Example result:
        FastAPI z GET /health i POST /anonymize

    Raises:
        EngineConfigError: `ANONYMIZATION_ENGINE` wskazuje silnik, którego ta wersja nie zna
    """
    settings = get_settings()

    _configure_logging(settings.log_level)

    # Tutaj, a nie przy pierwszym żądaniu: źle skonfigurowany silnik ma zabić kontener przy
    # starcie.
    engine = get_engine()

    app = FastAPI(
        title   = "dokus-anonymizer",
        version = "0.1.0",
    )

    # --- identyfikator żądania: przyjęty od `api`, a gdy go nie ma — nadany ---
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next) -> Response:
        """
        Description:
        Nadaje żądaniu identyfikator i odsyła go w nagłówku odpowiedzi. Identyfikator od
        wołającego wygrywa, żeby jeden spinał logi `api` i tej usługi.

        Example args:
            request=Request(scope={...})
            call_next=<następny element ASGI>

        Example result:
            Response z nagłówkiem X-Request-ID
        """
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex
        request.state.request_id = request_id

        started_at = time.perf_counter()
        response   = await call_next(request)
        elapsed_ms = (time.perf_counter() - started_at) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id

        # Identyfikatory i czasy, nigdy treść żądania: to surowe zgłoszenie.
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
    app.include_router(anonymize.router)

    # Ogłaszane przy starcie, bo silnik decyduje, czy `api` w ogóle przyjmie wynik.
    logger.info("anonymizer ready engine=%s", engine.name)

    return app


app = create_app()
