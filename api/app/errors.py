import logging
from collections.abc import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.db_postgres import DbPostgresConfigError, DbPostgresError
from app.db_qdrant import DbQdrantConfigError, DbQdrantError
from app.engine_anonymization import AnonymizationConfigError, AnonymizationError
from app.engine_embedding import EmbeddingConfigError, EmbeddingError
from app.engine_llm import LLMConfigError, LLMError
from app.engine_process import ProcessConfigError, ProcessError
from app.entry_routers.models import ErrorResponse

logger = logging.getLogger(__name__)

# Nagłówek, którym przyjmujemy identyfikator korelacji od wołającego i oddajemy ten, którego użyto.
REQUEST_ID_HEADER = "X-Request-ID"

# Awaria zależności w trakcie żądania to „chwilowo niedostępne", nie „błędne żądanie": konfigurację
# sprawdzono przy budowie klienta, więc zostaje to, co przejściowe (timeout, awaria dostawcy).
# 503 mówi wołającemu, że może ponowić, a helpdeskowi — że decyduje sam (fail-open po jego stronie).
DEPENDENCY_FAILURE_STATUS = 503

# Zależności narzędzi agenta: błąd warstwy → jego odmiana konfiguracyjna i opis dla wołającego.
# Jeden handler dla wszystkich, bo różni je tylko ten wiersz.
TOOL_DEPENDENCIES: dict[type[Exception], tuple[type[Exception], str]] = {
    EmbeddingError:  (EmbeddingConfigError,  "Embedding service call failed"),
    DbQdrantError:   (DbQdrantConfigError,   "Vector index call failed"),
    DbPostgresError: (DbPostgresConfigError, "Text index call failed"),
    ProcessError:    (ProcessConfigError,    "Code search call failed"),
}


def request_id_of(
    request: Request,  # np. Request z ustawionym state.request_id
) -> str | None:
    """
    Description:
    Czyta identyfikator korelacji zapisany na żądaniu przez middleware. Zwraca None, gdy handler
    działa bez tego middleware'u (np. naga aplikacja w teście), żeby obsługa błędu nie padała na
    braku identyfikatora. Czytają go handlery wyjątków i strumień przebiegu grafu.

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

    request_id = request_id_of(request)
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

    request_id = request_id_of(request)
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


def _llm_failure(
    exc:        Exception,   # np. LLMError("Read timed out after 60s")
    path:       str,         # np. "/search"
    request_id: str | None,  # np. "8f14e45fceea167a5a36dedd4bea2543"
) -> ErrorResponse:
    """
    Description:
    Opisuje awarię warstwy LLM: to, co rzuca SDK dostawcy, jest już przetłumaczone na
    `LLMError`, a tu przestaje być gołym 500. Komunikat celowo ogólny — tekst wyjątku dostawcy
    potrafi cytować prompt, czyli zgłoszenie klienta.

    Example args:
        exc=LLMError("Read timed out after 60s")
        path="/search"
        request_id="8f14e45fceea167a5a36dedd4bea2543"

    Example result:
        ErrorResponse(detail="Language model call failed", request_id="8f14…")

    Raises:
        LLMConfigError: puszczany dalej bez zmian — patrz niżej
    """
    # Błąd konfiguracji NIE może udawać chwilowej awarii: proces w ogóle nie powinien był zacząć
    # obsługiwać ruchu. Puszczony dalej kończy żądanie głośno (500 + stos), zamiast zostawić
    # zielony kontener oddający 503 każdemu wołającemu w nieskończoność.
    if isinstance(exc, LLMConfigError):
        raise exc

    # Treść wyjątku na ERROR, bo jest nasza (bez tekstu klienta) — w odróżnieniu od promptu.
    logger.error("llm_error path=%s error=%s request_id=%s", path, exc, request_id)

    return ErrorResponse(detail="Language model call failed", request_id=request_id)


def _anonymization_failure(
    exc:        Exception,   # np. AnonymizationError("usługa anonimizacji nie odpowiada")
    path:       str,         # np. "/search"
    request_id: str | None,  # np. "8f14e45fceea167a5a36dedd4bea2543"
) -> ErrorResponse:
    """
    Description:
    Opisuje porażkę anonimizacji. Graf staje przed modelem (fail-closed), więc nic nie wyszło —
    dla wołającego to awaria zależności, nie błędne żądanie, a o reszcie decyduje helpdesk.
    Treść wyjątku tylko w logu, bo anonimizator mógłby zacytować fragment tekstu.

    Example args:
        exc=AnonymizationError("usługa anonimizacji nie odpowiada")
        path="/search"
        request_id="8f14e45fceea167a5a36dedd4bea2543"

    Example result:
        ErrorResponse(detail="Anonymization failed", request_id="8f14…")

    Raises:
        AnonymizationConfigError: puszczany dalej bez zmian — z tego samego powodu co przy LLM
    """
    # Błąd konfiguracji (np. atrapa anonimizatora przy prawdziwym modelu) to nie stan przejściowy.
    if isinstance(exc, AnonymizationConfigError):
        raise exc

    # Bez treści wyjątku: komunikat anonimizatora może zawierać fragment danych klienta.
    logger.error(
        "anonymization_error path=%s error_type=%s request_id=%s",
        path,
        type(exc).__name__,
        request_id,
    )

    return ErrorResponse(detail="Anonymization failed", request_id=request_id)


def _tool_dependency_failure(
    exc:        Exception,   # np. DbQdrantError("Qdrant nie odpowiedział w czasie: POST /…")
    path:       str,         # np. "/search"
    request_id: str | None,  # np. "8f14e45fceea167a5a36dedd4bea2543"
) -> ErrorResponse:
    """
    Description:
    Opisuje awarię zależności, na których stoją narzędzia agenta: embeddera, Qdranta,
    Postgresa i programu, którym szuka się w kodzie. Węzeł `run_tools` takiego błędu nie łapie,
    więc przebieg grafu staje, a wołający dostaje opis, która zależność zawiodła.

    Example args:
        exc=DbQdrantError("Qdrant nie odpowiedział w czasie: POST /collections/tickets/…")
        path="/search"
        request_id="8f14e45fceea167a5a36dedd4bea2543"

    Example result:
        ErrorResponse(detail="Vector index call failed", request_id="8f14…")

    Raises:
        EmbeddingConfigError, DbQdrantConfigError, DbPostgresConfigError, ProcessConfigError:
            puszczane dalej bez zmian — z tego samego powodu co przy LLM
    """
    config_error, detail = next(
        entry for error, entry in TOOL_DEPENDENCIES.items() if isinstance(exc, error)
    )

    # Błąd konfiguracji (pusty adres, złe hasło, indeks z innej wersji kontraktu, brak programu
    # w obrazie) to nie stan przejściowy: czekanie go nie naprawi, więc kończy żądanie głośno.
    if isinstance(exc, config_error):
        raise exc

    # Treść wyjątku tylko na DEBUG: Qdrant, Postgres i ripgrep potrafią zacytować w błędzie
    # fragment zapytania, czyli dane klienta.
    logger.error(
        "tool_dependency_error path=%s error_type=%s request_id=%s",
        path,
        type(exc).__name__,
        request_id,
    )
    logger.debug("tool_dependency_error details=%s", exc)

    return ErrorResponse(detail=detail, request_id=request_id)


# Funkcja, która loguje awarię zależności i opisuje ją dla wołającego: (wyjątek, ścieżka, id).
DescribeFailure = Callable[[Exception, str, str | None], ErrorResponse]

# Awaria zależności: rodzina błędów warstwy → funkcja, która ją loguje i opisuje dla wołającego.
# Trzy funkcje zamiast jednej, bo każda warstwa inaczej pilnuje danych klienta w logu.
DEPENDENCY_FAILURES: dict[type[Exception], DescribeFailure] = {
    LLMError:           _llm_failure,
    AnonymizationError: _anonymization_failure,
    **{error: _tool_dependency_failure for error in TOOL_DEPENDENCIES},
}


def dependency_failure(
    exc:        Exception,   # np. EmbeddingError("embedder nie odpowiedział w czasie")
    path:       str,         # np. "/search"
    request_id: str | None,  # np. "8f14e45fceea167a5a36dedd4bea2543"
) -> ErrorResponse:
    """
    Description:
    Opisuje awarię zależności w trakcie żądania: loguje ją i oddaje błąd we wspólnym kształcie.
    Wołają ją handler poniżej, który odpowiada statusem 503, i strumień przebiegu grafu, który po
    wysłaniu nagłówków statusu już nie zmieni i oddaje błąd jako zdarzenie.

    Example args:
        exc=EmbeddingError("embedder nie odpowiedział w czasie")
        path="/search"
        request_id="8f14e45fceea167a5a36dedd4bea2543"

    Example result:
        ErrorResponse(detail="Embedding service call failed", request_id="8f14…")

    Raises:
        LLMConfigError, AnonymizationConfigError, EmbeddingConfigError, DbQdrantConfigError,
        DbPostgresConfigError, ProcessConfigError: błąd konfiguracji nie udaje chwilowej awarii
    """
    describe = next(
        failure for error, failure in DEPENDENCY_FAILURES.items() if isinstance(exc, error)
    )

    return describe(exc, path, request_id)


async def _handle_dependency_error(
    request: Request,    # np. Request(scope={...})
    exc:     Exception,  # np. LLMError("Read timed out after 60s")
) -> JSONResponse:
    """
    Description:
    Obsługuje awarię zależności: model, anonimizator i zależności narzędzi agenta. Wołający
    dostaje 503 we wspólnym kształcie błędu zamiast gołego 500, a o reszcie decyduje sam.

    Example args:
        request=Request(scope={...})
        exc=LLMError("Read timed out after 60s")

    Example result:
        JSONResponse(status_code=503, content={"detail": "Language model call failed", …})

    Raises:
        LLMConfigError, AnonymizationConfigError, EmbeddingConfigError, DbQdrantConfigError,
        DbPostgresConfigError, ProcessConfigError: puszczane dalej bez zmian
    """
    body = dependency_failure(exc, request.url.path, request_id_of(request))

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
    for error in DEPENDENCY_FAILURES:
        app.add_exception_handler(error, _handle_dependency_error)
