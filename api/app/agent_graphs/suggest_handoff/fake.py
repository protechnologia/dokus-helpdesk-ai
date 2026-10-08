from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.suggest_handoff.graph import build_graph
from app.agent_graphs.suggest_handoff.respond_tool import RESPOND_TOOL_NAME
from app.agent_graphs.suggest_handoff.state import SuggestHandoffState
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.core_model.graphs.proposal import Proposal
from app.engine_anonymization import FakeAnonymizer

# Propozycja atrapy, gdy nikt nie podał własnej — stała, żeby test, który przypadkiem na niej
# polega, padł głośno.
DEFAULT_PROPOSAL = Proposal(
    text           = "fake-suggest-handoff-proposal",
    internal_notes = "fake-suggest-handoff-notes",
)


def example_state() -> SuggestHandoffState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        SuggestHandoffState(input_text="Po aktualizacji nie działa podpis…")
    """
    state = SuggestHandoffState(
        input_text = "Po aktualizacji nie działa podpis. Sprawdzono certyfikat — jest ważny.",
    )

    return state


def build_fake_graph(
    proposal: Proposal = DEFAULT_PROPOSAL,  # np. Proposal(text="Przekazujemy…", …)
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent wywołuje
    `respond_suggest_handoff` z propozycją w argumentach, a `respond` oddaje tę propozycję.

    Graf jest jednorazowy: `FakeAgentNode` ma jedną turę. Na każde wywołanie buduj nowy.

    Example args:
        proposal=Proposal(text="Przekazujemy sprawę do serwisu…", internal_notes="")

    Example result:
        CompiledStateGraph, który na dowolne zgłoszenie oddaje `output` = podaną propozycję
    """
    answer = tool_call_turn(RESPOND_TOOL_NAME, proposal.model_dump())

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = FakeAgentNode([answer]),
        respond   = FakeRespondNode(proposal),
    )

    return graph
