from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs import gate_close, gate_reply
from app.agent_graphs.factory import get_graph_builder
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.core_model.graphs.verdict import Verdict
from app.core_service.loader_dict_rules import get_rule_set
from app.engine_anonymization import FakeAnonymizer
from app.main import create_app

# Kontrakt HTTP obu bramek w procesie: kształt werdyktu, furtka, wersja reguł i to, co trasa
# wkłada do stanu grafu. Trafność werdyktu mieszka w ewaluacji (p. 21–22), nie tutaj.

BLOCK = Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz, co zmieniono.")

TICKET = {"ticket_id": "41002", "body": "Nie przychodzą przesyłki z e-Doręczeń."}
REPLY  = {"ticket_id": "41002", "message": "Proszę podać hasło do skrzynki."}

# Zużycie modelu na atrapie: jedna tura, bez tokenów i kosztu.
ONE_FAKE_CALL = {
    "llm_calls":          1,
    "prompt_tokens":      0,
    "completion_tokens":  0,
    "cache_write_tokens": 0,
    "cache_read_tokens":  0,
    "cost_usd":           0.0,
}


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
    """Sprawdza, czy obie bramki (`/gate/close` i `/gate/reply`) oddają werdykt blokujący z grafu
    w pełnym kształcie: z uzasadnieniem, wskazówką, polem `overridable` równym `true`, wersją
    zestawu reguł tej bramki, zużyciem modelu i logiem przebiegu (anonimizacja, model, odpowiedź).

    Wyłapuje trasę, która gubi część werdyktu albo furtkę dla człowieka: helpdesk nie miałby
    wtedy czego pokazać przy blokadzie, nie wiedziałby, że wolno ją obejść, ani którą wersją
    reguł ją wydano."""
    graph_name = graph.__name__.split(".")[-1]
    response   = client_with(GateGraph(graph)).post(path, json=body)
    answer     = response.json()
    log        = answer.pop("log")

    assert response.status_code == 200
    assert [entry["node"] for entry in log] == ["anonymize", "agent", "respond"]
    assert answer == {
        "verdict":       "block",
        "reasons":       ["Nie widać, co zrobiono."],
        "missing":       [],
        "hint":          "Dopisz, co zmieniono.",
        "overridable":   True,
        "rules_version": get_rule_set(graph_name).version,
        "usage":         ONE_FAKE_CALL,
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
    """Sprawdza, czy przy żądaniu do każdej z bramek graf dostaje reguły z zestawu reguł tej
    właśnie bramki. Żądanie reguł nie podaje, dobiera je trasa.

    Wyłapuje trasę, która podaje grafowi inne reguły niż zestaw tej bramki, na przykład zestaw
    drugiej: werdykt oceniałby wtedy tekst według niewłaściwych wymagań."""
    gate       = GateGraph(graph)
    graph_name = graph.__name__.split(".")[-1]

    client_with(gate).post(path, json=body)

    assert gate.agent.calls[0].rules == get_rule_set(graph_name).rules


def test_the_close_gate_reads_the_whole_thread() -> None:
    """Sprawdza, czy bramka zamknięcia (`/gate/close`) podaje grafowi cały wątek zgłoszenia: tekst,
    który trafia do anonimizacji, zaczyna się od nagłówka „ZGŁOSZENIE 41002" i zawiera opis
    z żądania, czyli ma ten sam układ co przy parsowaniu zgłoszeń.

    Wyłapuje trasę, która przekazuje sam opis albo gubi numer zgłoszenia: bramka oceniałaby
    wtedy inny tekst niż ten, z którego później powstaje karta zgłoszenia."""
    gate = GateGraph(gate_close)

    client_with(gate).post("/gate/close", json=TICKET)

    assert gate.anonymizer.texts[0].startswith("ZGŁOSZENIE 41002")
    assert "Nie przychodzą przesyłki z e-Doręczeń." in gate.anonymizer.texts[0]


def test_the_reply_gate_reads_the_message_only() -> None:
    """Sprawdza, czy bramka wysyłki (`/gate/reply`) podaje grafowi samą wiadomość do klienta: do
    anonimizacji trafia dokładnie jeden tekst, równy wiadomości z żądania, bez numeru zgłoszenia
    i bez nagłówków wątku.

    Wyłapuje trasę, która dokleja do wiadomości coś od siebie: bramka oceniałaby wtedy inny
    tekst niż ten, który wdrożeniowiec chce wysłać."""
    gate = GateGraph(gate_reply)

    client_with(gate).post("/gate/reply", json=REPLY)

    assert gate.anonymizer.texts == ["Proszę podać hasło do skrzynki."]


@pytest.mark.parametrize(
    "path, body",
    [("/gate/close", {"ticket_id": "41002"}), ("/gate/reply", {"ticket_id": "41002"})],
    ids=["close-without-body", "reply-without-message"],
)
def test_a_request_without_content_is_refused(path: str, body: dict[str, str]) -> None:
    """Sprawdza, czy żądanie do bramki bez tekstu do oceny dostaje status 422: do `/gate/close`
    bez opisu zgłoszenia (pola `body`), a do `/gate/reply` bez wiadomości (pola `message`).

    Wyłapuje bramkę, która przyjmuje takie żądanie i uruchamia graf: werdykt wydany bez tekstu
    wyglądałby jak prawdziwa ocena."""
    response = TestClient(create_app()).post(path, json=body)

    assert response.status_code == 422
