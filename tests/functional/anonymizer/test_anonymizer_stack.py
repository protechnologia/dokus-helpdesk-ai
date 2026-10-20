import httpx2
import pytest

from tests._helpers.anonymization import RAW_TEXT

pytestmark = [pytest.mark.stack, pytest.mark.stack_anonymizer]

# Sam dym wdrożenia: kontrakt sprawdzają testy w procesie. Kontener dokłada dowód, że obraz się
# zbudował, CMD wskazuje właściwy moduł, a wystawiony port dociera do usługi.


def test_health_answers_over_the_published_port(anonymizer_service: httpx2.Client) -> None:
    """Sprawdza, czy uruchomiony kontener usługi `anonymizer` odpowiada na `GET /health` przez
    port wystawiony na hosta: status 200 i treść `{"status": "ok"}`.

    Wyłapuje usterkę wdrożenia, której testy w procesie nie widzą: obraz się nie zbudował,
    kontener uruchamia nie ten moduł albo port nie jest wystawiony."""
    response = anonymizer_service.get("/health")

    assert response.status_code == 200
    assert response.json()      == {"status": "ok"}


def test_anonymize_answers_with_text_and_engine(anonymizer_service: httpx2.Client) -> None:
    """Sprawdza, czy kontener odpowiada na `POST /anonymize` statusem 200 i treścią z dwoma
    niepustymi polami: tekstem i nazwą silnika.

    Wyłapuje kontener, który wstał, ale nie przyjmuje anonimizacji — na przykład z silnikiem,
    którego konfiguracja nie dotarła — co testy w procesie przeoczą, bo nie czytają compose."""
    response = anonymizer_service.post("/anonymize", json={"text": RAW_TEXT})
    body     = response.json()

    assert response.status_code == 200
    assert set(body)            == {"text", "engine"}
    assert body["text"] and body["engine"]


def test_info_names_the_engine_of_the_container(anonymizer_service: httpx2.Client) -> None:
    """Sprawdza, czy kontener odpowiada na `GET /info` statusem 200 i dwoma polami: niepustą
    nazwą silnika i modelem, który przy silniku `agent` jest niepusty.

    Wyłapuje kontener ze starego obrazu, w którym trasy jeszcze nie ma: `GET /instance` w `api`
    pokazywałby anonimizator jako niedostępny, choć usługa działa."""
    response = anonymizer_service.get("/info")
    body     = response.json()

    assert response.status_code == 200
    assert set(body)            == {"engine", "model"}
    assert body["engine"]
    assert body["engine"] != "agent" or body["model"]
