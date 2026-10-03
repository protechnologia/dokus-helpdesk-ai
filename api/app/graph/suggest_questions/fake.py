from langgraph.graph.state import CompiledStateGraph

from app.anonymization import FakeAnonymizer
from app.graph.fake import fake_search_nodes
from app.graph.suggest_questions.graph import build_graph
from app.graph.suggest_questions.respond_tool import RESPOND_TOOL_NAME
from app.graph.suggest_questions.state import SuggestQuestionsState
from app.model.suggest_proposal import Proposal
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespondNode

# Propozycja atrapy, gdy nikt nie podał własnej — stała, żeby test, który przypadkiem na niej
# polega, padł głośno.
DEFAULT_PROPOSAL = Proposal(text="fake-suggest-questions-proposal")


def example_state() -> SuggestQuestionsState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        SuggestQuestionsState(input_text="Od wczoraj nie przychodzą przesyłki z e-…")
    """
    state = SuggestQuestionsState(
        input_text = "Od wczoraj nie przychodzą przesyłki z e-Doręczeń, inne skrzynki działają.",
    )

    return state


def build_fake_graph(
    proposal: Proposal = DEFAULT_PROPOSAL,  # np. Proposal(text="…")
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent najpierw szuka
    `find_tickets_vector` (trzy zgłoszenia o jednym objawie i trzech przyczynach), potem wywołuje
    `respond_suggest_questions` z propozycją w argumentach; w stanie zostają trzy źródła.

    Graf jest jednorazowy: `FakeAgentNode` ma zaplanowane tury. Na każde wywołanie buduj nowy.

    Example args:
        proposal=Proposal(text="…")

    Example result:
        CompiledStateGraph, który na dowolne zgłoszenie oddaje `output` = podaną propozycję
    """
    agent, run_tools = fake_search_nodes(RESPOND_TOOL_NAME, proposal)

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = agent,
        run_tools = run_tools,
        respond   = FakeRespondNode(proposal),
    )

    return graph
