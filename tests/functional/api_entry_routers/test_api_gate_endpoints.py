from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs import gate_close, gate_reply
from app.agent_graphs.factory import get_graph_builder
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.core_model.gate_verdict import Verdict
from app.core_service.loader_dict_rules import get_rule_set
from app.engine_anonymization import FakeAnonymizer
from app.main import create_app

# Kontrakt HTTP obu bramek w procesie: kształt werdyktu, furtka, wersja reguł i to, co trasa
# wkłada do stanu grafu. Trafność werdyktu mieszka w ewaluacji (p. 21–22), nie tutaj.

BLOCK = Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz, co zmieniono.")

TICKET = {"ticket_id": "41002", "body": "Nie przychodzą przesyłki z e-Doręczeń."}
REPLY  = {"ticket_id": "41002", "message": "Proszę podać hasło do skrzynki."}


class GateGraph:
    """Graf bramki z atrap, do których test ma dostęp: anonimizator zapisuje wejście, agent stan."""

    def __init__(
        self,
        graph: ModuleType,  # np. app.agent_graphs.gate_close
    ) -> None:
        """
        Description:
        Składa graf bramki, który oddaje werdykt `BLOCK` wywołaniem jej narzędzia odpowiedzi.

        Example args:
            graph=app.agent_graphs.gate_close

        Example result:
            GateGraph z publicznymi `anonymizer`, `agent` i `compiled`
        """
        self.anonymizer = FakeAnonymizer()
        self.agent      = FakeAgentNode(
            [tool_call_turn(graph.RESPOND_TOOL_NAME, BLOCK.model_dump())]
        )
        self.compiled: CompiledStateGraph = graph.build_graph(
            AnonymizeNode(self.anonymizer),
            self.agent,
            FakeRespondNode(BLOCK),
        )


def client_with(
    gate: GateGraph,  # np. GateGraph(gate_close)
) -> TestClient:
    """
    Description:
    Aplikacja, w której fabryka grafów oddaje podany graf bramki.

    Example args:
        gate=GateGraph(gate_close)

    Example result:
        TestClient nad aplikacją z podmienioną fabryką grafów
    """
    app = create_app()
    app.dependency_overrides[get_graph_builder] = lambda: (lambda module: gate.compiled)

    return TestClient(app)


@pytest.mark.parametrize(
    "graph, path, body",
    [(gate_close, "/gate/close", TICKET), (gate_reply, "/gate/reply", REPLY)],
    ids=["close", "reply"],
)
def test_the_verdict_goes_out_with_the_override_and_the_rules_version(
    graph: ModuleType,
    path:  str,
    body:  dict[str, str],
) -> None:
    """Werdykt grafu → odpowiedź z uzasadnieniem i wskazówką, `overridable` = true (zasada 10)
    i wersją zestawu reguł, którą go wydano."""
    graph_name = graph.__name__.split(".")[-1]
    response   = client_with(GateGraph(graph)).post(path, json=body)

    assert response.status_code == 200
    assert response.json() == {
        "verdict":       "block",
        "reasons":       ["Nie widać, co zrobiono."],
        "missing":       [],
        "hint":          "Dopisz, co zmieniono.",
        "overridable":   True,
        "rules_version": get_rule_set(graph_name).version,
    }


@pytest.mark.parametrize(
    "graph, path, body",
    [(gate_close, "/gate/close", TICKET), (gate_reply, "/gate/reply", REPLY)],
    ids=["close", "reply"],
)
def test_the_rules_come_from_the_rule_set_of_the_gate(
    graph: ModuleType,
    path:  str,
    body:  dict[str, str],
) -> None:
    """Żądanie → stan grafu z regułami z zestawu tej bramki, nie z żądania."""
    gate       = GateGraph(graph)
    graph_name = graph.__name__.split(".")[-1]

    client_with(gate).post(path, json=body)

    assert gate.agent.calls[0].rules == get_rule_set(graph_name).rules


def test_the_close_gate_reads_the_whole_thread() -> None:
    """`/gate/close` → wejście grafu to wątek zgłoszenia z id i opisem, jak przy parsowaniu."""
    gate = GateGraph(gate_close)

    client_with(gate).post("/gate/close", json=TICKET)

    assert gate.anonymizer.texts[0].startswith("ZGŁOSZENIE 41002")
    assert "Nie przychodzą przesyłki z e-Doręczeń." in gate.anonymizer.texts[0]


def test_the_reply_gate_reads_the_message_only() -> None:
    """`/gate/reply` → wejście grafu to sama wiadomość do klienta."""
    gate = GateGraph(gate_reply)

    client_with(gate).post("/gate/reply", json=REPLY)

    assert gate.anonymizer.texts == ["Proszę podać hasło do skrzynki."]


@pytest.mark.parametrize(
    "path, body",
    [("/gate/close", {"ticket_id": "41002"}), ("/gate/reply", {"ticket_id": "41002"})],
    ids=["close-without-body", "reply-without-message"],
)
def test_a_request_without_content_is_refused(path: str, body: dict[str, str]) -> None:
    """Żądanie bez treści do oceny → 422, zanim cokolwiek dotknie grafu."""
    response = TestClient(create_app()).post(path, json=body)

    assert response.status_code == 422
