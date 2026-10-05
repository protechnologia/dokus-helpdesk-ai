from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    """Sprawdza, czy `GET /health` w świeżo złożonej aplikacji `api` odpowiada statusem 200
    i treścią `{"status": "ok"}`.

    Wyłapuje aplikację, która się nie składa albo nie ma podpiętej trasy `/health`: na tej
    odpowiedzi opiera się sprawdzanie, czy kontener żyje."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_body_exposes_no_configuration() -> None:
    """Sprawdza, czy odpowiedź `GET /health` usługi `api` ma tylko jedno pole, `status`.

    Wyłapuje dopisanie do tej odpowiedzi czegokolwiek o konfiguracji: `/health` jest dostępne dla
    każdego, kto dosięgnie usługi, więc nie może zdradzać dostawców, adresów ani modeli."""
    client = TestClient(create_app())

    response = client.get("/health")

    assert set(response.json()) == {"status"}
