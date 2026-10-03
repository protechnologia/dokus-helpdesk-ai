from langgraph.graph.state import CompiledStateGraph

from app.anonymization import FakeAnonymizer
from app.graph.fake import fake_search_nodes
from app.graph.search.graph import build_graph
from app.graph.search.models import SearchDone
from app.graph.search.respond_tool import RESPOND_TOOL_NAME
from app.graph.search.state import SearchState
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespond


def example_state() -> SearchState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        SearchState(input_text="Od wczoraj nie przychodzą przesyłki…")
    """
    state = SearchState(
        input_text = "Od wczoraj nie przychodzą przesyłki z e-Doręczeń, nadawcy mówią, że wysłali.",
    )

    return state


def build_fake_graph() -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent najpierw szuka
    `find_tickets_vector` (trzy zgłoszenia o jednym objawie i trzech przyczynach), potem wywołuje
    `respond_search`; w stanie zostają trzy źródła i jedno zapytanie agenta.

    Graf jest jednorazowy: `FakeAgent` ma zaplanowane tury. Na każde wywołanie buduj nowy.

    Example args:
        (brak)

    Example result:
        CompiledStateGraph: anonymize → agent → run_tools → agent → respond
    """
    agent, run_tools = fake_search_nodes(RESPOND_TOOL_NAME, SearchDone())

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = agent,
        run_tools = run_tools,
        respond   = FakeRespond(SearchDone()),
    )

    return graph
