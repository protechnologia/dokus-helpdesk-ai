from fastapi.testclient import TestClient

from anonymizer_app.core_engine import AgentEngine, get_engine
from anonymizer_app.main import create_app
from tests._helpers.anonymization import FAKE_ENGINE
from tests._helpers.anonymizer_llm import MODEL_BASE_URL, MODEL_NAME, model_client_on
from tests._helpers.transport import always


def test_the_fake_engine_is_described_without_a_model() -> None:
    """Sprawdza, czy `GET /info` na domyślnej atrapie silnika odpowiada statusem 200, nazwą
    silnika „fake" i modelem `null`.

    Wyłapuje opis, który podaje model przy atrapie: belka frontu mówiłaby, że zgłoszenia
    anonimizuje model, choć usługa oddaje tekst bez zmian."""
    response = TestClient(create_app()).get("/info")

    assert response.status_code == 200
    assert response.json()      == {"engine": FAKE_ENGINE, "model": None}


def test_the_agent_engine_is_described_without_asking_the_model() -> None:
    """Sprawdza, czy `GET /info` na silniku `agent` podaje jego nazwę i nazwę modelu
    anonimizującego, także gdy serwer modelu odpowiada błędem, i nie podaje adresu serwera.

    Wyłapuje opis, który pyta model (przy wyłączonym podzie z GPU belka nie pokazałaby nic) albo
    wystawia adres serwera modelu: trasę osiągnie każdy, kto dosięgnie portu usługi."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: AgentEngine(
        model_client_on(always({"error": "pod down"}, status=502)),
    )

    response = TestClient(app).get("/info")

    assert response.status_code == 200
    assert response.json()      == {"engine": "agent", "model": MODEL_NAME}
    assert MODEL_BASE_URL not in response.text
