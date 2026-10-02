from fastapi.testclient import TestClient

from app.graph import parse_ticket
from app.main import create_app

# Kontrakt HTTP `POST /parse-ticket`: karta zgłoszenia pole po polu, bez pól wewnętrznych.

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}


def test_the_card_goes_out_field_by_field() -> None:
    """Atrapa grafu → karta z polami korpusu; wersja słownika rozstrzygnięć zostaje w domenie."""
    response = TestClient(create_app()).post("/parse-ticket", json=TICKET)
    expected = parse_ticket.default_ticket().model_dump(
        mode    = "json",
        exclude = {"resolution_vocabulary_version"},
    )

    assert response.status_code == 200
    assert response.json() == expected


def test_a_ticket_without_body_is_refused() -> None:
    """Żądanie bez `body` → 422, zanim cokolwiek dotknie grafu."""
    response = TestClient(create_app()).post("/parse-ticket", json={"ticket_id": "41002"})

    assert response.status_code == 422
