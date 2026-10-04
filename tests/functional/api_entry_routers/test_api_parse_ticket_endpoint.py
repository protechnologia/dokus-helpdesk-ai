from fastapi.testclient import TestClient

from app.agent_graphs import parse_ticket
from app.agent_graphs.factory import get_graph_builder
from app.agent_nodes.agent import FakeAgentNode
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.engine_anonymization import FakeAnonymizer
from app.main import create_app

# Kontrakt HTTP `POST /parse-ticket`: karta zgłoszenia pole po polu, bez pól wewnętrznych.

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}


def test_the_card_goes_out_field_by_field() -> None:
    """Atrapa grafu → karta z polami korpusu i zużyciem modelu; wersja słownika rozstrzygnięć
    zostaje w domenie."""
    response = TestClient(create_app()).post("/parse-ticket", json=TICKET)
    expected = parse_ticket.default_ticket().model_dump(
        mode    = "json",
        exclude = {"resolution_vocabulary_version"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body.pop("usage")["llm_calls"] == 1
    assert body == expected


def test_a_ticket_without_body_is_refused() -> None:
    """Żądanie bez `body` → 422, zanim cokolwiek dotknie grafu."""
    response = TestClient(create_app()).post("/parse-ticket", json={"ticket_id": "41002"})

    assert response.status_code == 422


def test_the_route_puts_the_ticket_identity_into_the_state() -> None:
    """`/parse-ticket` → id i data zgłoszenia z żądania trafiają do stanu, nie do modelu."""
    agent = FakeAgentNode()
    graph = parse_ticket.build_graph(
        AnonymizeNode(FakeAnonymizer()),
        agent,
        FakeRespondNode(parse_ticket.default_ticket()),
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    TestClient(app).post(
        "/parse-ticket",
        json={"ticket_id": "41002", "date": "2026-08-19", "body": "Nie działa wysyłka."},
    )

    assert (agent.calls[0].ticket_id, agent.calls[0].date.isoformat()) == ("41002", "2026-08-19")
