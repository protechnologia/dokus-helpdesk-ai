from fastapi.testclient import TestClient

from app.main import create_app

# Kontrakt HTTP `POST /polish`: tekst do akceptacji człowieka.


def test_the_polished_text_goes_out() -> None:
    """Sprawdza, czy `POST /polish` z notatkami wdrożeniowca oddaje tekst z grafu „Popraw" (tu
    stały tekst atrapy) razem ze zużyciem modelu (jedno wywołanie, koszt zero) i logiem przebiegu:
    anonimizacja, model, odpowiedź.

    Wyłapuje trasę, która nie oddaje wyniku grafu albo gubi zużycie i log: wdrożeniowiec nie
    dostałby poprawionego tekstu do akceptacji, a wołający nie widziałby kosztu ani przebiegu."""
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
    """Sprawdza, czy `POST /polish` z pustym tekstem notatek dostaje status 422.

    Wyłapuje trasę, która przyjmuje puste notatki i uruchamia graf: nie ma w nich czego
    poprawiać, więc każdy tekst, który by wrócił, byłby zmyślony."""
    response = TestClient(create_app()).post("/polish", json={"ticket_id": "41002", "text": ""})

    assert response.status_code == 422
