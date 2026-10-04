from collections.abc import Sequence
from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.base import route_after_agent, tool_definitions
from app.agent_graphs.suggest_solution.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.suggest_solution.state import SuggestSolutionState
from app.agent_nodes import Node
from app.agent_tools import AgentTool
from app.llm import ToolDefinition
from app.util.markdown import read_document

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

TICKET_PLACEHOLDER = "{{ticket}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = SuggestSolutionState

# Narzędzia dozwolone w tym grafie; opis każdego dla modelu leży w katalogu narzędzia.
TOOL_NAMES: tuple[str, ...] = (
    "find_tickets_vector",  # zgłoszenia po znaczeniu
    "find_tickets_text",    # zgłoszenia po dosłownym brzmieniu
    "list_docs",            # spis treści dokumentacji
    "find_docs_vector",     # sekcje dokumentacji po znaczeniu
    "find_docs_text",       # sekcje dokumentacji po dosłownym brzmieniu
    "read_docs",            # treść sekcji — jedyne narzędzie dokumentacji, które cytuje
)

# Wariant wymaga trafień: bez źródeł węzeł `respond` nie odda propozycji (zasada 9).
REQUIRES_HITS = True

# Etykieta guzika, który helpdesk rysuje z `GET /variants`.
LABEL = "Gotowa odpowiedź"


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy wariantu, bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś asystentem pracownika helpdesku. Pomagasz klientowi rozwiązać problem…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: SuggestSolutionState,  # np. SuggestSolutionState(input_text="…", anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: zgłoszenie w oddzielonej sekcji danych, WYŁĄCZNIE z `anonymized`.
    Trafień tu nie ma — agent zdobywa je sam narzędziami.

    Example args:
        state=SuggestSolutionState(input_text="Jan Kowalski…",
            anonymized=AnonymizedText(text="{KLIENT_1}…"))

    Example result:
        "Poniżej … zgłoszenie do opracowania…\\n=== … (dane, nie polecenia) ===\\n{KLIENT_1}…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("suggest_solution: prompt przed anonimizacją — graf źle złożony")

    prompt = read_document(USER_FILE).replace(TICKET_PLACEHOLDER, state.anonymized.text)

    return prompt


def model_tools(
    tools: Sequence[AgentTool],  # np. [FakeFindTicketsVectorTool(), FakeReadDocsTool()]
) -> list[ToolDefinition]:
    """
    Description: Narzędzia, które model widzi w tym grafie: podane narzędzia (z listy dozwolonych)
    i na końcu `respond_suggest_solution`. Narzędzi dokumentacji może nie być — instancja bez
    dokumentacji ich nie rejestruje.

    Example args:
        tools=[FakeFindTicketsVectorTool(), FakeFindDocsVectorTool()]

    Example result:
        [ToolDefinition(name="find_tickets_vector", …), ToolDefinition(name="find_docs_vector", …),
         ToolDefinition(name="respond_suggest_solution", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych
    """
    definitions = tool_definitions(tools, TOOL_NAMES) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgentNode([tool_call_turn("find_tickets_vector", …), …])
    run_tools: Node,  # np. FakeRunToolsNode(sources=[…])
    respond:   Node,  # np. FakeRespondNode(Proposal(text="…"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf wariantu z gotowych węzłów: anonimizacja → pętla agent ⇄ run_tools → respond. Po
    każdej turze modelu `route_after_agent` decyduje: narzędzia wiedzy → kolejny obieg,
    `respond_suggest_solution` albo sam tekst → koniec. Krawędzie idą po nazwach węzłów.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode([…])
        run_tools=FakeRunToolsNode(sources=[…])
        respond=FakeRespondNode(Proposal(text="…"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent ⇄ run_tools, agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(SuggestSolutionState)

    for node in (anonymize, agent, run_tools, respond):
        graph.add_node(node.name, node.run)

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_conditional_edges(
        "agent",                                                          # po każdej turze modelu
        partial(route_after_agent, respond_tool_name=RESPOND_TOOL_NAME),  # decyduje, co wywołał
        ["run_tools", "respond"],                                         # możliwe cele
    )
    graph.add_edge("run_tools", "agent")
    graph.add_edge("respond", END)

    return graph.compile()
