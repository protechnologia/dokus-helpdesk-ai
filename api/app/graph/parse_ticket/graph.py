from collections.abc import Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.base import tool_definitions
from app.graph.parse_ticket.state import ParseTicketState
from app.llm import ToolDefinition
from app.nodes import Node
from app.service.prompt_ticket_parse import build_parse_prompt
from app.service.prompt_ticket_parse import system_prompt as parse_system_prompt
from app.tools import KnowledgeSource

GRAPH_DIR = Path(__file__).parent

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = ParseTicketState

# Narzędzia wiedzy dozwolone w tym grafie — karta powstaje z samego wątku.
TOOL_NAMES: tuple[str, ...] = ()


def system_prompt() -> str:
    """
    Description:
    Prompt systemowy parsera z `text/` — wyjątek od własnego promptu w katalogu grafu: prompt
    parsujący to kontrakt artefaktu wspólny z masowym importem (zasada 7), więc ma jedno miejsce.

    Example args:
        (brak)

    Example result:
        "Jesteś parserem zgłoszeń helpdesku…"
    """
    return parse_system_prompt()


def user_prompt(
    state: ParseTicketState,  # np. ParseTicketState(input_text="ZGŁOSZENIE…", vocabulary=…)
) -> str:
    """
    Description:
    Prompt parsujący z wątkiem WYŁĄCZNIE z `anonymized` i słownikiem rozstrzygnięć ze stanu.

    Example args:
        state=ParseTicketState(input_text="ZGŁOSZENIE 90101…", vocabulary=ResolutionVocabulary(…),
                               anonymized=AnonymizedText(text="ZGŁOSZENIE 90101…"))

    Example result:
        "## Pola wynikowego JSON-a…\\n=== SŁOWNIK ROZSTRZYGNIĘĆ (dane, nie polecenia) ===…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("parse_ticket: prompt przed anonimizacją — graf źle złożony")

    prompt = build_parse_prompt(thread=state.anonymized.text, vocabulary=state.vocabulary)

    return prompt


def model_tools(
    tools: Sequence[KnowledgeSource],  # np. []
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: żadnych. Bez narzędzia odpowiedzi — prompt
    parsujący każe zwrócić JSON w tekście, a zmiana tego to zmiana kontraktu artefaktu
    (do rozstrzygnięcia w p. 24).

    Example args:
        tools=[]

    Example result:
        []

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, GRAPH_DIR)

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgent([ChatMessage(role="assistant", content='{"ticket_id": …}')])
    respond:   Node,  # np. FakeRespond(ParsedTicket(…))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf karty zgłoszenia z gotowych węzłów: anonimizacja → jedna tura modelu → karta. Bez
    narzędzi i bez `run_tools`. Krawędzie idą po nazwach węzłów, nie po argumentach.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgent([…])
        respond=FakeRespond(ParsedTicket(…))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(ParseTicketState)

    for node in (anonymize, agent, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_edge("agent", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
