from fastapi.testclient import TestClient

from app.anonymization import FakeAnonymizer
from app.factory import get_graph_builder
from app.graph import search
from app.graph.fake import FAKE_SEARCH_ARGUMENTS, fake_search_nodes
from app.main import create_app
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespondNode

# Kontrakt HTTP `POST /search` w procesie: kształt odpowiedzi (źródła + zapytania agenta),
# walidacja żądania i to, co trasa wkłada do grafu. Że trasa jest zamontowana w obrazie, sprawdza
# `stack_api`.

TICKET = {"ticket_id": "41002", "body": "Od wczoraj nie przychodzą przesyłki z e-Doręczeń."}


def test_sources_and_agent_queries_go_out() -> None:
    """Atrapa grafu `search` → źródła z `cite()` i zapytanie agenta; wywołanie `respond_search`
    nie jest zapytaniem, więc go w odpowiedzi nie ma."""
    response = TestClient(create_app()).post("/search", json=TICKET)

    assert response.status_code == 200
    assert [item["item_id"] for item in response.json()["sources"]] == ["90001", "90002", "90003"]
    assert response.json()["queries"] == [
        {"tool": "find_tickets_vector", "arguments": FAKE_SEARCH_ARGUMENTS},
    ]


def test_the_graph_reads_the_whole_thread() -> None:
    """Żądanie → wejście grafu to wątek zgłoszenia z id i opisem, w formacie parsera korpusu."""
    anonymizer       = FakeAnonymizer()
    agent, run_tools = fake_search_nodes(search.RESPOND_TOOL_NAME, search.SearchDone())
    graph            = search.build_graph(
        AnonymizeNode(anonymizer),
        agent,
        run_tools,
        FakeRespondNode(search.SearchDone()),
    )

    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: graph)

    TestClient(app).post("/search", json=TICKET)

    assert anonymizer.texts[0].startswith("ZGŁOSZENIE 41002")
    assert "Od wczoraj nie przychodzą przesyłki" in anonymizer.texts[0]


def test_a_ticket_without_body_is_refused() -> None:
    """Żądanie bez `body` → 422, zanim cokolwiek dotknie grafu."""
    response = TestClient(create_app()).post("/search", json={"ticket_id": "41002"})

    assert response.status_code == 422
