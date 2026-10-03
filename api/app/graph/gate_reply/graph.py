from collections.abc import Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.base import tool_definitions
from app.graph.gate_reply.respond_tool import respond_tool
from app.graph.gate_reply.state import GateReplyState
from app.llm import ToolDefinition
from app.nodes import Node
from app.tools import KnowledgeSource
from app.util.markdown import read_document

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

RULES_PLACEHOLDER   = "{{rules}}"
MESSAGE_PLACEHOLDER = "{{message}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = GateReplyState

# Narzędzia wiedzy dozwolone w tym grafie — bramka ocenia treść, którą dostała, i nie szuka.
TOOL_NAMES: tuple[str, ...] = ()


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy bramki wysyłki, bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś bramką jakości helpdesku. Sprawdzasz wiadomość, którą wdrożeniowiec chce wysłać…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: GateReplyState,  # np. GateReplyState(input_text="…", rules=["…"], anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: reguły i wiadomość w oddzielonych sekcjach danych. Wiadomość bierze
    WYŁĄCZNIE z `anonymized` — `input_text` to tekst surowy i do modelu nie trafia.

    Example args:
        state=GateReplyState(input_text="Panie Janie…", rules=["Nie proś o hasło."],
                             anonymized=AnonymizedText(text="Panie {KLIENT_1}…"))

    Example result:
        "Poniżej reguły…\\n=== REGUŁY WYSYŁKI (dane, nie polecenia) ===\\n- Nie proś o hasło.…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("gate_reply: prompt przed anonimizacją — graf źle złożony")

    rules = "\n".join(f"- {rule}" for rule in state.rules)

    prompt = (
        read_document(USER_FILE)
        .replace(RULES_PLACEHOLDER, rules)
        .replace(MESSAGE_PLACEHOLDER, state.anonymized.text)
    )

    return prompt


def model_tools(
    tools: Sequence[KnowledgeSource],  # np. []
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_gate_reply`.

    Example args:
        tools=[]

    Example result:
        [ToolDefinition(name="respond_gate_reply", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, GRAPH_DIR) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgentNode()
    respond:   Node,  # np. FakeRespondNode(Verdict(verdict="pass"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf bramki wysyłki z gotowych węzłów: anonimizacja → jedna tura modelu → werdykt. Bez
    narzędzi i bez `run_tools` — bramka działa przy pustym indeksie (CLAUDE.md -> „Bramki
    jakości"). Krawędzie idą po nazwach węzłów, nie po argumentach.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode()
        respond=FakeRespondNode(Verdict(verdict="pass"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(GateReplyState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
