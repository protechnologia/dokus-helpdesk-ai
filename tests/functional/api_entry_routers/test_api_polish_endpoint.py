from fastapi.testclient import TestClient

from app.main import create_app

# Kontrakt HTTP `POST /polish`: tekst do akceptacji człowieka.


def test_the_polished_text_goes_out() -> None:
    """Notatki → tekst z atrapy grafu `polish`."""
    response = TestClient(create_app()).post(
        "/polish",
        json={"ticket_id": "41002", "text": "przesylki juz ida"},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "fake-polish-text"}


def test_empty_notes_are_refused() -> None:
    """Puste notatki → 422: nie ma czego poprawiać."""
    response = TestClient(create_app()).post("/polish", json={"ticket_id": "41002", "text": ""})

    assert response.status_code == 422
