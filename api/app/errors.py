import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.anonymization import AnonymizationConfigError, AnonymizationError
from app.llm import LLMConfigError, LLMError
from app.models import ErrorResponse

logger = logging.getLogger(__name__)

# Nagłówek, którym przyjmujemy identyfikator korelacji od wołającego i oddajemy ten, którego użyto.
REQUEST_ID_HEADER = "X-Request-ID"

# Awaria zależności w trakcie żądania to „chwilowo niedostępne", nie „błędne żądanie": konfigurację
# sprawdzono przy budowie klienta, więc zostaje to, co przejściowe (timeout, awaria dostawcy).
# 503 mówi wołającemu, że może ponowić, a helpdeskowi — że decyduje sam (fail-open po jego stronie).
DEPENDENCY_FAILURE_STATUS = 503


def _request_id_of(
    request: Request,  # np. Request z ustawionym state.request_id
) -> str | None:
    """
    Description:
    Czyta identyfikator korelacji zapisany na żądaniu przez middleware. Zwraca None, gdy handler
    działa bez tego middleware'u (np. naga aplikacja w teście), żeby obsługa błędu nie padała na
    braku identyfikatora.

    Example args:
        request=Request(scope={...})

    Example result:
        "8f14e45fceea167a5a36dedd4bea2543"
    """
    return getattr(request.state, "request_id", None)


async def _handle_http_exception(
    request: Request,    # np. Request(scope={...})
    exc:     Exception,  # np. HTTPException(status_code=404, detail="Ticket not found")
) -> JSONResponse:
    """
    Description:
    Zamienia `HTTPException` na wspólny kształt błędu. Przyczynę logujemy TUTAJ, nie
    w middleware: middleware widzi gotową `Response`, której treść niczego już nie tłumaczy,
    a `detail` — jedyne „dlaczego" — żyje w wyjątku.

    Example args:
        request=Request(scope={...})
        exc=HTTPException(status_code=404, detail="Ticket not found")

    Example result:
        JSONResponse(status_code=404, content={"detail": "Ticket not found", "request_id": "8f14…"})
    """
    # Sygnatura z `Exception`, bo rejestr handlerów FastAPI jest nietypowany; zawężamy tutaj.
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


async def _handle_validation_error(
    request: Request,    # np. Request(scope={...})
    exc:     Exception,  # np. RequestValidationError(errors=[…])
) -> JSONResponse:
    """
    Description:
    Obsługuje `RequestValidationError` — najczęstsze 422. To NIE jest `HTTPException`, więc bez
    własnego handlera ominęłoby ten wyżej i oddało surowy kształt błędu FastAPI.

    Example args:
        request=Request(scope={...})
        exc=RequestValidationError(errors=[{"loc": ["body", "ticket_id"], "msg": "…"}])

    Example result:
        JSONResponse(status_code=422, content={"detail": "…", "request_id": "8f14…"})
    """
    assert isinstance(exc, RequestValidationError)

    request_id = _request_id_of(request)
    # Pełna lista błędów tylko na DEBUG: cytuje przysłane wartości, czyli potencjalnie dane klienta.
    logger.warning(
        "validation_error path=%s error_count=%d request_id=%s",
        request.url.path,
        len(exc.errors()),
        request_id,
    )
    logger.debug("validation_error details=%s", exc.errors())

    body = ErrorResponse(detail="Request validation failed", request_id=request_id)

    return JSONResponse(status_code=422, content=body.model_dump())


async def _handle_llm_error(
    request: Request,    # np. Request(scope={...})
    exc:     Exception,  # np. LLMError("Read timed out after 60s")
) -> JSONResponse:
    """
    Description:
    Obsługuje awarię warstwy LLM: to, co rzuca SDK dostawcy, jest już przetłumaczone na
    `LLMError`, a tu przestaje być gołym 500. Komunikat celowo ogólny — tekst wyjątku dostawcy
    potrafi cytować prompt, czyli zgłoszenie klienta.

    Example args:
        request=Request(scope={...})
        exc=LLMError("Read timed out after 60s")

    Example result:
        JSONResponse(status_code=503, content={"detail": "Language model call failed", …})

    Raises:
        LLMConfigError: puszczany dalej bez zmian — patrz niżej
    """
    # Błąd konfiguracji NIE może udawać chwilowej awarii: proces w ogóle nie powinien był zacząć
    # obsługiwać ruchu. Puszczony dalej kończy żądanie głośno (500 + stos), zamiast zostawić
    # zielony kontener oddający 503 każdemu wołającemu w nieskończoność.
    if isinstance(exc, LLMConfigError):
        raise exc

    assert isinstance(exc, LLMError)

    request_id = _request_id_of(request)
    # Treść wyjątku na ERROR, bo jest nasza (bez tekstu klienta) — w odróżnieniu od promptu.
    logger.error(
        "llm_error path=%s error=%s request_id=%s",
        request.url.path,
        exc,
        request_id,
    )

    body = ErrorResponse(detail="Language model call failed", request_id=request_id)

    return JSONResponse(status_code=DEPENDENCY_FAILURE_STATUS, content=body.model_dump())


async def _handle_anonymization_error(
    request: Request,    # np. Request(scope={...})
    exc:     Exception,  # np. AnonymizationError("usługa anonimizacji nie odpowiada")
) -> JSONResponse:
    """
    Description:
    Obsługuje porażkę anonimizacji. Graf staje przed modelem (fail-closed), więc nic nie wyszło —
    dla wołającego to awaria zależności, nie błędne żądanie: 503, a o reszcie decyduje helpdesk.
    Treść wyjątku tylko w logu, bo anonimizator mógłby zacytować fragment tekstu.

    Example args:
        request=Request(scope={...})
        exc=AnonymizationError("usługa anonimizacji nie odpowiada")

    Example result:
        JSONResponse(status_code=503, content={"detail": "Anonymization failed", …})

    Raises:
        AnonymizationConfigError: puszczany dalej bez zmian — z tego samego powodu co przy LLM
    """
    # Błąd konfiguracji (np. atrapa anonimizatora przy prawdziwym modelu) to nie stan przejściowy.
    if isinstance(exc, AnonymizationConfigError):
        raise exc

    assert isinstance(exc, AnonymizationError)

    request_id = _request_id_of(request)
    # Bez treści wyjątku: komunikat anonimizatora może zawierać fragment danych klienta.
    logger.error(
        "anonymization_error path=%s error_type=%s request_id=%s",
        request.url.path,
        type(exc).__name__,
        request_id,
    )

    body = ErrorResponse(detail="Anonymization failed", request_id=request_id)

    return JSONResponse(status_code=DEPENDENCY_FAILURE_STATUS, content=body.model_dump())


def register_exception_handlers(
    app: FastAPI,  # np. FastAPI()
) -> None:
    """
    Description:
    Rejestruje wszystkie handlery wyjątków na aplikacji. Oddzielone od montażu aplikacji, żeby test
    mógł podpiąć je do nagiej aplikacji i sprawdzić bez prawdziwych tras.

    Example args:
        app=FastAPI()

    Example result:
        None — aplikacja odpowiada kształtem ErrorResponse dla każdej obsłużonej awarii
    """
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    # Rejestrowane zawsze, nie „gdy powstanie pierwszy wołający": to handler sprawia, że awaria
    # zależności jest udokumentowanym 503, a nie tym, co autor trasy akurat pamiętał złapać.
    app.add_exception_handler(LLMError, _handle_llm_error)
    app.add_exception_handler(AnonymizationError, _handle_anonymization_error)
