from collections.abc import Mapping

from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.fake import fake_search_nodes
from app.agent_graphs.search.graph import build_graph
from app.agent_graphs.search.models import SearchDone
from app.agent_graphs.search.respond_tool import RESPOND_TOOL_NAME
from app.agent_graphs.search.state import SearchState
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.engine_anonymization import FakeAnonymizer


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


def build_fake_graph(
    limits: Mapping[str, int] | None = None,  # np. {"read_tickets_card": 3}
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent najpierw szuka
    `find_tickets_vector`, potem czyta karty znalezionych zgłoszeń `read_tickets_card` (jeden
    objaw, trzy przyczyny) i wywołuje `respond_search`; w stanie zostają trzy źródła z odczytu
    i dwa wywołania narzędzi.

    Graf jest jednorazowy: `FakeAgentNode` ma zaplanowane tury. Na każde wywołanie buduj nowy.
    `limits` to limity wywołań narzędzi; bez nich atrapa niczego nie odmawia.

    Example args:
        limits={"find_tickets_vector": 3, "read_tickets_card": 3}

    Example result:
        CompiledStateGraph: anonymize → agent ⇄ run_tools (szukaj, czytaj) → respond
    """
    agent, run_tools = fake_search_nodes(RESPOND_TOOL_NAME, SearchDone(), limits)

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = agent,
        run_tools = run_tools,
        respond   = FakeRespondNode(SearchDone()),
    )

    return graph
