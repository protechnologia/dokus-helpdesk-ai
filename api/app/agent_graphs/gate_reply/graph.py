from collections.abc import Mapping, Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.base import route_after_respond, tool_definitions
from app.agent_graphs.gate_reply.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.gate_reply.state import GateReplyState
from app.agent_nodes import Node
from app.agent_nodes.respond import RespondNode
from app.agent_tools import KnowledgeSource
from app.core_model.graphs.verdict import Verdict
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

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
    tools:  Sequence[KnowledgeSource],  # np. []
    limits: Mapping[str, int],          # np. {"find_tickets_vector": 3}
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_gate_reply`.

    Example args:
        tools=[]
        limits={}

    Example result:
        [ToolDefinition(name="respond_gate_reply", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, limits) + [respond_tool()]

    return definitions


def respond_node() -> RespondNode:
    """
    Description:
    Węzeł odpowiedzi tego grafu: waliduje argumenty `respond_gate_reply` do `Verdict`. Blokada
    bez uzasadnienia albo bez wskazówki nie przechodzi walidacji i wraca do modelu do poprawki
    (zasada 10).

    Example args:
        (brak)

    Example result:
        RespondNode czytający wywołanie `respond_gate_reply` jako `Verdict`
    """
    node = RespondNode(
        respond_tool_name = RESPOND_TOOL_NAME,
        output_model      = Verdict,
    )

    return node


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

    Po `respond` przebieg się kończy, chyba że węzeł odesłał odpowiedź modelowi do poprawki —
    wtedy model dostaje jeszcze jedną turę (`route_after_respond`).

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode()
        respond=FakeRespondNode(Verdict(verdict="pass"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__,
        respond → agent przy poprawce

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(GateReplyState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_conditional_edges(
        "respond",            # po odczytaniu odpowiedzi modelu
        route_after_respond,  # odpowiedź odesłana do poprawki → jeszcze jedna tura modelu
        ["agent", END],       # możliwe cele
    )

    return graph.compile()
