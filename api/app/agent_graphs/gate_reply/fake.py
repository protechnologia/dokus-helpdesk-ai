from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.gate_reply.graph import build_graph
from app.agent_graphs.gate_reply.respond_tool import RESPOND_TOOL_NAME
from app.agent_graphs.gate_reply.state import GateReplyState
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.engine_anonymization import FakeAnonymizer
from app.model.gate_verdict import Verdict

# Werdykt atrapy, gdy nikt nie podał własnego — stały, żeby test, który przypadkiem na nim polega,
# padł głośno.
DEFAULT_VERDICT = Verdict(verdict="pass", reasons=["fake-gate-reply-verdict"])


def example_state() -> GateReplyState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        GateReplyState(input_text="Dzień dobry, proszę podać…", rules=["Nie proś o hasło.", …])
    """
    state = GateReplyState(
        input_text = "Dzień dobry, proszę podać hasło do skrzynki, sprawdzimy konfigurację.",
        rules      = ["Nie proś klienta o hasło ani login.", "Bez potocznego słownictwa."],
    )

    return state


def build_fake_graph(
    verdict: Verdict = DEFAULT_VERDICT,  # np. Verdict(verdict="block", reasons=["…"], hint="…")
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent wywołuje
    `respond_gate_reply` z werdyktem w argumentach, a `respond` oddaje ten werdykt.

    Graf jest jednorazowy: `FakeAgentNode` ma jedną turę. Na każde wywołanie buduj nowy.

    Example args:
        verdict=Verdict(verdict="block", reasons=["Prośba o hasło."], hint="Usuń prośbę o hasło.")

    Example result:
        CompiledStateGraph, który na dowolną wiadomość oddaje `output` = podany werdykt
    """
    answer = tool_call_turn(RESPOND_TOOL_NAME, verdict.model_dump())

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = FakeAgentNode([answer]),
        respond   = FakeRespondNode(verdict),
    )

    return graph
