from fastapi.testclient import TestClient

from app.anonymization import AnonymizedText, FakeAnonymizer
from app.factory import get_graph_builder
from app.graph.parse_ticket import (
    FILLED_BY_GRAPH,
    build_graph,
    default_ticket,
    example_state,
    respond_tool,
    user_prompt,
)
from app.graph.parse_ticket.graph import build_parse_prompt
from app.main import create_app
from app.nodes.agent import FakeAgent
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespond


def test_the_graph_prompt_is_the_parsing_prompt_with_the_anonymized_thread() -> None:
    """Tura użytkownika grafu → prompt parsujący z wątkiem po anonimizacji i słownikiem ze stanu."""
    state = example_state().model_copy(update={"anonymized": AnonymizedText(text="ZGŁOSZENIE 1")})

    assert user_prompt(state) == build_parse_prompt("ZGŁOSZENIE 1", state.vocabulary)


def test_the_model_is_not_asked_for_what_the_graph_fills() -> None:
    """Pola tożsamości, daty i wersji słownika → poza schematem narzędzia odpowiedzi: model, który
    by je wymyślił, nie ma jak ich podać, a graf bierze je ze stanu."""
    assert not set(FILLED_BY_GRAPH) & set(respond_tool().parameters["properties"])


def test_the_route_puts_the_ticket_identity_into_the_state() -> None:
    """`/parse-ticket` → id i data zgłoszenia z żądania trafiają do stanu, nie do modelu."""
    agent = FakeAgent()
    graph = build_graph(AnonymizeNode(FakeAnonymizer()), agent, FakeRespond(default_ticket()))

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    TestClient(app).post(
        "/parse-ticket",
        json={"ticket_id": "41002", "date": "2026-08-19", "body": "Nie działa wysyłka."},
    )

    assert (agent.calls[0].ticket_id, agent.calls[0].date.isoformat()) == ("41002", "2026-08-19")
