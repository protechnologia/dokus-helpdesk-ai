from fastapi.testclient import TestClient

from embedder_app.main import create_app


def test_health_returns_ok() -> None:
    """Sprawdza, czy `GET /health` w świeżo złożonej aplikacji embeddera odpowiada statusem 200
    i treścią `{"status": "ok"}`.

    Wyłapuje aplikację, która się nie składa albo nie ma podpiętej trasy `/health`: na tej
    odpowiedzi opiera się sprawdzanie, czy kontener żyje."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_body_exposes_no_configuration() -> None:
    """Sprawdza, czy odpowiedź `GET /health` embeddera ma tylko jedno pole, `status`.

    Wyłapuje dopisanie do tej odpowiedzi nazwy modelu albo wymiaru wektora: usługa je zna,
    a `/health` jest dostępne dla każdego, kto dosięgnie portu."""
    client = TestClient(create_app())

    response = client.get("/health")

    # This service knows the model name and the vector width, so the temptation to expose them on
    # a public liveness probe is real — and the probe is reachable by anyone who reaches the port.
    assert set(response.json()) == {"status"}
