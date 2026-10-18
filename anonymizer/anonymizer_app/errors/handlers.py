import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from anonymizer_app.errors.engine_config_error import EngineConfigError
from anonymizer_app.errors.engine_error import EngineError
from anonymizer_app.models.error_response import ErrorResponse

logger = logging.getLogger(__name__)

# Nagłówek, którym przyjmujemy identyfikator żądania od wołającego i oddajemy ten, którego
# użyliśmy. Wołającym jest `api`: jeden identyfikator ma spinać logi obu usług.
REQUEST_ID_HEADER = "X-Request-ID"

# Awaria silnika to „chwilowo niedostępne", a nie „błędne żądanie": konfigurację sprawdza start
# usługi, więc w trakcie żądania zostaje już tylko awaria przejściowa.
ENGINE_FAILURE_STATUS = 503

# Każdy błąd tej usługi kończy się bez treści żądania i bez komunikatu biblioteki: wejściem jest
# surowe zgłoszenie z danymi osobowymi, a komunikat biblioteki potrafi je zacytować.


def _request_id_of(request: Request) -> str | None:  # np. Request z ustawionym state.request_id
    """
    Description:
    Czyta identyfikator żądania zapisany przez middleware. Oddaje `None`, gdy handler działa bez
    tego middleware (naga aplikacja w teście), więc obsługa błędu nie pada przez brak id.

    Example args:
        request=Request(scope={...})

    Example result:
        "8f14e45fceea167a5a36dedd4bea2543"
    """
    return getattr(request.state, "request_id", None)


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Description:
    Zamienia `HTTPException` na wspólny kształt błędu i zapisuje przyczynę w logu — tutaj, a nie
    w middleware, bo tylko wyjątek niesie `detail`.

    Example args:
        request=Request(scope={...})
        exc=HTTPException(status_code=404, detail="Not Found")

    Example result:
        JSONResponse(status_code=404, content={"detail": "Not Found", "request_id": "8f14…"})
    """
    # Rejestr handlerów FastAPI nie zna typów, więc zawężamy tutaj.
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
    Obsługuje `RequestValidationError`, czyli 422 na przykład przy pustym tekście. To nie jest
    `HTTPException`, więc bez własnego handlera FastAPI oddałoby swój surowy kształt błędu. Lista
    błędów nie trafia do logu na żadnym poziomie, inaczej niż w `embedder`: cytuje przysłane
    wartości, czyli surowe zgłoszenie.

    Example args:
        request=Request(scope={...})
        exc=RequestValidationError(errors=[{"loc": ["body", "text"], "msg": "…"}])

    Example result:
        JSONResponse(status_code=422, content={"detail": "Request validation failed", …})
    """
    assert isinstance(exc, RequestValidationError)

    request_id = _request_id_of(request)
    logger.warning(
        "validation_error path=%s error_count=%d request_id=%s",
        request.url.path,
        len(exc.errors()),
        request_id,
    )

    body = ErrorResponse(detail="Request validation failed", request_id=request_id)

    return JSONResponse(status_code=422, content=body.model_dump())


async def _handle_engine_error(request: Request, exc: Exception) -> JSONResponse:
    """
    Description:
    Obsługuje awarię silnika: 503 z ogólnym opisem. Do logu idzie sam typ wyjątku, bez
    komunikatu — biblioteka prawdziwego silnika (NER) potrafi zacytować w nim tekst wejściowy.

    Example args:
        request=Request(scope={...})
        exc=EngineError("model NER nie odpowiedział")

    Example result:
        JSONResponse(status_code=503, content={"detail": "Anonymization failed", …})

    Raises:
        EngineConfigError: puszczany dalej bez zmian — niżej dlaczego
    """
    # `EngineConfigError` dziedziczy po `EngineError`, więc trafiłby tutaj. Nie może: błąd
    # konfiguracji znaczy, że usługa nie powinna w ogóle odpowiadać, a uprzejme 503 kazałoby
    # wołającemu czekać na coś, czego czekanie nie naprawi.
    if isinstance(exc, EngineConfigError):
        raise exc

    assert isinstance(exc, EngineError)

    request_id = _request_id_of(request)
    logger.error(
        "engine_error path=%s error_type=%s request_id=%s",
        request.url.path,
        type(exc).__name__,
        request_id,
    )

    body = ErrorResponse(detail="Anonymization failed", request_id=request_id)

    return JSONResponse(status_code=ENGINE_FAILURE_STATUS, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:  # np. FastAPI()
    """
    Description:
    Rejestruje wszystkie handlery wyjątków. Osobno od składania aplikacji, żeby test mógł podpiąć
    je do nagiej aplikacji i sprawdzić bez prawdziwych tras.

    Example args:
        app=FastAPI()

    Example result:
        None — aplikacja odpowiada kształtem `ErrorResponse` na każdy obsłużony błąd
    """
    app.add_exception_handler(HTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(EngineError, _handle_engine_error)
