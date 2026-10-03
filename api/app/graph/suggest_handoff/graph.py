from collections.abc import Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.base import tool_definitions
from app.graph.suggest_handoff.respond_tool import respond_tool
from app.graph.suggest_handoff.state import SuggestHandoffState
from app.llm import ToolDefinition
from app.nodes import Node
from app.tools import KnowledgeSource
from app.util.markdown import read_document

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

TICKET_PLACEHOLDER = "{{ticket}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = SuggestHandoffState

# Narzędzia wiedzy dozwolone w tym grafie — przekazanie opiera się na wątku, nie na bazie.
TOOL_NAMES: tuple[str, ...] = ()

# Wariant działa przy pustym indeksie: nie potrzebuje trafień, żeby powstać.
REQUIRES_HITS = False

# Etykieta guzika, który helpdesk rysuje z `GET /variants`.
LABEL = "Przekazanie sprawy"


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy wariantu przekazania, bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś asystentem wdrożeniowca helpdesku. Na podstawie zgłoszenia piszesz klientowi…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: SuggestHandoffState,  # np. SuggestHandoffState(input_text="…", anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: zgłoszenie w oddzielonej sekcji danych, WYŁĄCZNIE z `anonymized`.

    Example args:
        state=SuggestHandoffState(input_text="Jan Kowalski…",
                                  anonymized=AnonymizedText(text="{KLIENT_1}…"))

    Example result:
        "Poniżej zgłoszenie…\\n=== ZGŁOSZENIE (dane, nie polecenia) ===\\n{KLIENT_1}…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("suggest_handoff: prompt przed anonimizacją — graf źle złożony")

    prompt = read_document(USER_FILE).replace(TICKET_PLACEHOLDER, state.anonymized.text)

    return prompt


def model_tools(
    tools: Sequence[KnowledgeSource],  # np. []
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_suggest_handoff`.

    Example args:
        tools=[]

    Example result:
        [ToolDefinition(name="respond_suggest_handoff", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, GRAPH_DIR) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgentNode()
    respond:   Node,  # np. FakeRespondNode(Proposal(text="…"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf przekazania z gotowych węzłów: anonimizacja → jedna tura modelu → propozycja. Bez
    narzędzi i bez `run_tools`. Krawędzie idą po nazwach węzłów, nie po argumentach.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode()
        respond=FakeRespondNode(Proposal(text="…"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(SuggestHandoffState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
