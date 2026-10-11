from collections.abc import Mapping

from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.fake import FAKE_MAX_ITERATIONS, fake_search_nodes
from app.agent_graphs.search.graph import build_graph
from app.agent_graphs.search.models import SearchNotes
from app.agent_graphs.search.respond_tool import RESPOND_TOOL_NAME
from app.agent_graphs.search.state import SearchState
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.engine_anonymization import FakeAnonymizer

# Uwagi atrapy, gdy nikt nie podał własnych — stałe, żeby test, który przypadkiem na nich
# polega, padł głośno.
DEFAULT_NOTES = SearchNotes(internal_notes="fake-search-notes")


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
    notes:          SearchNotes = DEFAULT_NOTES,      # np. SearchNotes(internal_notes="…")
    limits:         Mapping[str, int] | None = None,  # np. {"read_tickets_card": 3}
    max_iterations: int = FAKE_MAX_ITERATIONS,        # np. 2 — limit tur modelu
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent najpierw szuka
    `find_tickets_vector`, potem czyta karty znalezionych zgłoszeń `read_tickets_card` (jeden
    objaw, trzy przyczyny) i wywołuje `respond_search` z uwagami w argumentach; w stanie
    zostają trzy źródła z odczytu, dwa wywołania narzędzi i podane uwagi.

    Graf jest jednorazowy: `FakeAgentNode` ma zaplanowane tury. Na każde wywołanie buduj nowy.
    `limits` to limity wywołań narzędzi; bez nich atrapa niczego nie odmawia.
    `max_iterations` to limit tur modelu: po tylu turach narzędzia nie są już wykonywane.

    Example args:
        notes=SearchNotes(internal_notes="## Zgłoszenia historyczne\n- 90001 (2026-02-10): …")
        limits={"find_tickets_vector": 3, "read_tickets_card": 3}
        max_iterations=10

    Example result:
        CompiledStateGraph, który na dowolne zgłoszenie oddaje `output` = podane uwagi
    """
    agent, run_tools = fake_search_nodes(RESPOND_TOOL_NAME, notes, limits)

    graph = build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = agent,
        run_tools      = run_tools,
        respond        = FakeRespondNode(notes),
        max_iterations = max_iterations,
    )

    return graph
