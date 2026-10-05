import httpx2
import pytest

from app.errors import REQUEST_ID_HEADER

pytestmark = [pytest.mark.stack, pytest.mark.stack_api]

# This is the DEPLOYMENT half of the split from CLAUDE.md -> "Testy". Nothing here re-checks the
# response shape — unit tests on TestClient already prove that, and repeating it would only make
# the marked run longer. What only a container can prove is that the image built, the CMD points
# at the right module, the published port reaches it and the environment arrived.


def test_health_answers_over_the_published_port(api_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener `api` odpowiada na `GET /health` przez port wystawiony
    na hosta: status 200 i treść `{"status": "ok"}`.

    Wyłapuje usterkę wdrożenia, której testy w procesie nie widzą: obraz się nie zbudował,
    kontener uruchamia nie ten moduł albo port nie jest wystawiony."""
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_response_carries_a_request_id(api_client: httpx2.Client) -> None:
    """Sprawdza, czy odpowiedź uruchomionego kontenera `api` niesie niepusty nagłówek
    `X-Request-ID` z identyfikatorem żądania.

    Wyłapuje wdrożenie, w którym warstwa nadająca identyfikator żądania nie jest podpięta:
    wpisów logu jednego żądania nie dałoby się wtedy ze sobą powiązać."""
    response = api_client.get("/health")

    assert response.headers.get(REQUEST_ID_HEADER)


def test_request_id_from_the_caller_is_echoed_back(api_client: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener `api` odsyła bez zmian identyfikator, który wołający
    podał w nagłówku `X-Request-ID`.

    Wyłapuje usługę, która nadpisuje przysłany identyfikator własnym: jeden identyfikator ma
    łączyć wpisy tego samego żądania w logach kilku usług, a po podmianie ślad urywałby się na
    `api`."""
    correlation_id = "integration-smoke-0e2"

    response = api_client.get("/health", headers={REQUEST_ID_HEADER: correlation_id})

    assert response.headers.get(REQUEST_ID_HEADER) == correlation_id
