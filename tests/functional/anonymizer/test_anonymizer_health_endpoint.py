from fastapi.testclient import TestClient

from anonymizer_app.main import create_app


def test_health_returns_ok() -> None:
    """Sprawdza, czy `GET /health` w świeżo złożonej usłudze `anonymizer` odpowiada statusem 200
    i treścią `{"status": "ok"}`.

    Wyłapuje usługę, która się nie składa albo nie ma podpiętej trasy `/health`: na tej
    odpowiedzi opiera się sprawdzanie, czy kontener żyje."""
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json()      == {"status": "ok"}


def test_health_exposes_no_configuration() -> None:
    """Sprawdza, czy odpowiedź `GET /health` usługi `anonymizer` ma tylko jedno pole, `status`.

    Wyłapuje dopisanie do sondy nazwy silnika: sondę osiągnie każdy, kto dosięgnie portu, a ta
    usługa przyjmuje surowe zgłoszenia."""
    response = TestClient(create_app()).get("/health")

    assert set(response.json()) == {"status"}
