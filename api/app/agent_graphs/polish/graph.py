from collections.abc import Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.base import tool_definitions
from app.agent_graphs.polish.respond_tool import respond_tool
from app.agent_graphs.polish.state import PolishState
from app.agent_nodes import Node
from app.agent_tools import KnowledgeSource
from app.llm import ToolDefinition
from app.util.markdown import read_document

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

RULES_PLACEHOLDER = "{{rules}}"
DRAFT_PLACEHOLDER = "{{draft}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = PolishState

# Narzędzia wiedzy dozwolone w tym grafie — „Popraw" działa przy pustym indeksie.
TOOL_NAMES: tuple[str, ...] = ()


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy „Popraw", bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś redaktorem wiadomości helpdesku. Przepisujesz notatki wdrożeniowca…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: PolishState,  # np. PolishState(input_text="…", rules=["…"], anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: zasady stylu i notatki w oddzielonych sekcjach danych. Notatki bierze
    WYŁĄCZNIE z `anonymized` — `input_text` to tekst surowy i do modelu nie trafia.

    Example args:
        state=PolishState(input_text="jan, przesylki juz ida", rules=["Zwracaj się per Państwo."],
                          anonymized=AnonymizedText(text="{KLIENT_1}, przesylki juz ida"))

    Example result:
        "Poniżej zasady stylu…\\n=== ZASADY STYLU (dane, nie polecenia) ===\\n- Zwracaj się…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("polish: prompt przed anonimizacją — graf źle złożony")

    rules = "\n".join(f"- {rule}" for rule in state.rules)

    prompt = (
        read_document(USER_FILE)
        .replace(RULES_PLACEHOLDER, rules)
        .replace(DRAFT_PLACEHOLDER, state.anonymized.text)
    )

    return prompt


def model_tools(
    tools: Sequence[KnowledgeSource],  # np. []
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_polish`.

    Example args:
        tools=[]

    Example result:
        [ToolDefinition(name="respond_polish", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgentNode()
    respond:   Node,  # np. FakeRespondNode(PolishedText(text="…"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf „Popraw" z gotowych węzłów: anonimizacja → jedna tura modelu → tekst. Bez narzędzi
    i bez `run_tools`. Krawędzie idą po nazwach węzłów, nie po argumentach.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode()
        respond=FakeRespondNode(PolishedText(text="…"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(PolishState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
