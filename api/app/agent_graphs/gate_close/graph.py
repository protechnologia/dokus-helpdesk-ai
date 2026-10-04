from collections.abc import Mapping, Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.base import tool_definitions
from app.agent_graphs.gate_close.respond_tool import respond_tool
from app.agent_graphs.gate_close.state import GateCloseState
from app.agent_nodes import Node
from app.agent_tools import KnowledgeSource
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

RULES_PLACEHOLDER  = "{{rules}}"
TICKET_PLACEHOLDER = "{{ticket}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = GateCloseState

# Narzędzia wiedzy dozwolone w tym grafie — bramka ocenia treść, którą dostała, i nie szuka.
TOOL_NAMES: tuple[str, ...] = ()


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy bramki, bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś bramką jakości helpdesku. Oceniasz, czy zgłoszenie można zamknąć…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: GateCloseState,  # np. GateCloseState(input_text="…", rules=["…"], anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: reguły i zgłoszenie w oddzielonych sekcjach danych. Zgłoszenie bierze
    WYŁĄCZNIE z `anonymized` — `input_text` to tekst surowy i do modelu nie trafia.

    Example args:
        state=GateCloseState(input_text="Jan Kowalski…", rules=["Opis musi wskazywać problem."],
                             anonymized=AnonymizedText(text="{KLIENT_1}…"))

    Example result:
        "Poniżej reguły…\\n=== REGUŁY ZAMKNIĘCIA (dane, nie polecenia) ===\\n- Opis musi…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("gate_close: prompt przed anonimizacją — graf źle złożony")

    rules = "\n".join(f"- {rule}" for rule in state.rules)

    prompt = (
        read_document(USER_FILE)
        .replace(RULES_PLACEHOLDER, rules)
        .replace(TICKET_PLACEHOLDER, state.anonymized.text)
    )

    return prompt


def model_tools(
    tools:  Sequence[KnowledgeSource],  # np. []
    limits: Mapping[str, int],          # np. {"find_tickets_vector": 3}
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_gate_close`.

    Example args:
        tools=[]
        limits={}

    Example result:
        [ToolDefinition(name="respond_gate_close", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, limits) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgentNode()
    respond:   Node,  # np. FakeRespondNode(Verdict(verdict="pass"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf bramki zamknięcia z gotowych węzłów: anonimizacja → jedna tura modelu → werdykt.
    Bez narzędzi i bez `run_tools`, więc bez pętli — bramka ocenia treść, którą dostała, i nie
    sięga do indeksu (CLAUDE.md -> „Bramki jakości").

    Krawędzie idą po nazwach węzłów, nie po argumentach: węzły zamienione miejscami dają ten sam
    graf, a dwa węzły o jednej nazwie — błąd przy składaniu.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode()
        respond=FakeRespondNode(Verdict(verdict="pass"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(GateCloseState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
