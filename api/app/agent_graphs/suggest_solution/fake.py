from collections.abc import Mapping

from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.fake import fake_search_nodes
from app.agent_graphs.suggest_solution.graph import build_graph
from app.agent_graphs.suggest_solution.respond_tool import RESPOND_TOOL_NAME
from app.agent_graphs.suggest_solution.state import SuggestSolutionState
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.core_model.graphs.proposal import Proposal
from app.engine_anonymization import FakeAnonymizer

# Propozycja atrapy, gdy nikt nie podał własnej — stała, żeby test, który przypadkiem na niej
# polega, padł głośno.
DEFAULT_PROPOSAL = Proposal(text="fake-suggest-solution-proposal")


def example_state() -> SuggestSolutionState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        SuggestSolutionState(input_text="Nie przychodzą przesyłki z e-Doręczeń od…")
    """
    state = SuggestSolutionState(
        input_text = "Nie przychodzą przesyłki z e-Doręczeń od czasu wczorajszej aktualizacji.",
    )

    return state


def build_fake_graph(
    proposal: Proposal = DEFAULT_PROPOSAL,      # np. Proposal(text="…")
    limits:   Mapping[str, int] | None = None,  # np. {"read_tickets_card": 3}
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent najpierw szuka
    `find_tickets_vector`, potem czyta karty znalezionych zgłoszeń `read_tickets_card` (jeden
    objaw, trzy przyczyny) i wywołuje `respond_suggest_solution` z propozycją
    w argumentach; w stanie zostają trzy źródła z odczytu.

    Graf jest jednorazowy: `FakeAgentNode` ma zaplanowane tury. Na każde wywołanie buduj nowy.
    `limits` to limity wywołań narzędzi; bez nich atrapa niczego nie odmawia.

    Example args:
        proposal=Proposal(text="…")
        limits={"find_tickets_vector": 3, "read_tickets_card": 3}

    Example result:
        CompiledStateGraph, który na dowolne zgłoszenie oddaje `output` = podaną propozycję
    """
    agent, run_tools = fake_search_nodes(RESPOND_TOOL_NAME, proposal, limits)

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = agent,
        run_tools = run_tools,
        respond   = FakeRespondNode(proposal),
    )

    return graph
