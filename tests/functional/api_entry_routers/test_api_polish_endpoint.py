from fastapi.testclient import TestClient

from app.main import create_app

# Kontrakt HTTP `POST /polish`: tekst do akceptacji człowieka.


def test_the_polished_text_goes_out() -> None:
    """Notatki → tekst z atrapy grafu `polish`, ze zużyciem modelu i logiem przebiegu."""
    response = TestClient(create_app()).post(
        "/polish",
        json={"ticket_id": "41002", "text": "przesylki juz ida"},
    )

    body = response.json()

    assert response.status_code == 200
    assert body["text"]               == "fake-polish-text"
    assert body["usage"]["llm_calls"] == 1
    assert body["usage"]["cost_usd"]  == 0.0
    assert [entry["node"] for entry in body["log"]] == ["anonymize", "agent", "respond"]


def test_empty_notes_are_refused() -> None:
    """Puste notatki → 422: nie ma czego poprawiać."""
    response = TestClient(create_app()).post("/polish", json={"ticket_id": "41002", "text": ""})

    assert response.status_code == 422
