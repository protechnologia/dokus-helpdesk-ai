from langgraph.graph.state import CompiledStateGraph

from app.anonymization import FakeAnonymizer
from app.graph.gate_close.graph import build_graph
from app.graph.gate_close.respond_tool import RESPOND_TOOL_NAME
from app.graph.gate_close.state import GateCloseState
from app.model.gate_verdict import Verdict
from app.nodes.agent import FakeAgentNode, tool_call_turn
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespondNode

# Werdykt atrapy, gdy nikt nie podał własnego — stały, żeby test, który przypadkiem na nim polega,
# padł głośno.
DEFAULT_VERDICT = Verdict(verdict="pass", reasons=["fake-gate-close-verdict"])


def example_state() -> GateCloseState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        GateCloseState(input_text="Nie przychodzą przesyłki…", rules=["Opis musi…", …])
    """
    state = GateCloseState(
        input_text = "Nie przychodzą przesyłki z e-Doręczeń. Zrestartowano usługę odbioru.",
        rules      = ["Opis wskazuje problem.", "Opis mówi, co zrobiono."],
    )

    return state


def build_fake_graph(
    verdict: Verdict = DEFAULT_VERDICT,  # np. Verdict(verdict="block", reasons=["…"], hint="…")
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Anonimizacja jest
    prawdziwym węzłem na `FakeAnonymizer`, agent wywołuje `respond_gate_close` z werdyktem
    w argumentach, a `respond` oddaje ten werdykt.

    Graf jest jednorazowy: `FakeAgentNode` ma jedną turę, więc drugie wywołanie tego samego grafu
    kończy się błędem. Na każde wywołanie buduj nowy.

    Example args:
        verdict=Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz…")

    Example result:
        CompiledStateGraph, który na dowolne zgłoszenie oddaje `output` = podany werdykt
    """
    answer = tool_call_turn(RESPOND_TOOL_NAME, verdict.model_dump())

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = FakeAgentNode([answer]),
        respond   = FakeRespondNode(verdict),
    )

    return graph
