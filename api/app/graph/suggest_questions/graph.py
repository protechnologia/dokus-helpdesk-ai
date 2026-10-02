from collections.abc import Sequence
from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.base import route_after_agent, tool_definitions
from app.graph.suggest_questions.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.graph.suggest_questions.state import SuggestQuestionsState
from app.llm import ToolDefinition
from app.nodes import Node
from app.tools import KnowledgeSource
from app.util.markdown import read_document

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

TICKET_PLACEHOLDER = "{{ticket}}"

# Narzędzia wiedzy dozwolone w tym grafie; opis każdego dla modelu leży obok jako `<nazwa>.md`.
TOOL_NAMES: tuple[str, ...] = ("find_tickets", "find_docs")

# Wariant działa przy pustym indeksie — trafienia wzbogacają pytania, ale nie są konieczne.
REQUIRES_HITS = False


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy wariantu, bez komentarzy redakcyjnych.

    Example args:
        (brak)

    Example result:
        "Jesteś asystentem wdrożeniowca helpdesku. Z nowego zgłoszenia i z podobnych spraw…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def user_prompt(
    state: SuggestQuestionsState,  # np. SuggestQuestionsState(input_text="…", anonymized=…)
) -> str:
    """
    Description:
    Składa turę użytkownika: zgłoszenie w oddzielonej sekcji danych, WYŁĄCZNIE z `anonymized`.
    Trafień tu nie ma — agent zdobywa je sam narzędziami.

    Example args:
        state=SuggestQuestionsState(input_text="Jan Kowalski…",
            anonymized=AnonymizedText(text="{KLIENT_1}…"))

    Example result:
        "Poniżej … zgłoszenie do opracowania…\\n=== … (dane, nie polecenia) ===\\n{KLIENT_1}…"

    Raises:
        ValueError: stan jeszcze nie przeszedł anonimizacji
    """
    if state.anonymized is None:
        raise ValueError("suggest_questions: prompt przed anonimizacją — graf źle złożony")

    prompt = read_document(USER_FILE).replace(TICKET_PLACEHOLDER, state.anonymized.text)

    return prompt


def model_tools(
    tools: Sequence[KnowledgeSource],  # np. [FakeFindTickets(), FakeFindDocs()]
) -> list[ToolDefinition]:
    """
    Description:
    Narzędzia, które model widzi w tym grafie: podane narzędzia wiedzy (z listy dozwolonych) i na
    końcu `respond_suggest_questions`.

    Example args:
        tools=[FakeFindTickets(), FakeFindDocs()]

    Example result:
        [ToolDefinition(name="find_tickets", …), ToolDefinition(name="find_docs", …),
         ToolDefinition(name="respond_suggest_questions", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych
    """
    definitions = tool_definitions(tools, TOOL_NAMES, GRAPH_DIR) + [respond_tool()]

    return definitions


def build_graph(
    anonymize: Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:     Node,  # np. FakeAgent([tool_call_turn("find_tickets", …), …])
    run_tools: Node,  # np. FakeRunTools(sources=[…])
    respond:   Node,  # np. FakeRespond(Proposal(text="…"))
) -> CompiledStateGraph:
    """
    Description:
    Składa graf wariantu z gotowych węzłów: anonimizacja → pętla agent ⇄ run_tools → respond. Po
    każdej turze modelu `route_after_agent` decyduje: narzędzia wiedzy → kolejny obieg,
    `respond_suggest_questions` albo sam tekst → koniec. Krawędzie idą po nazwach węzłów.

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgent([…])
        run_tools=FakeRunTools(sources=[…])
        respond=FakeRespond(Proposal(text="…"))

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent ⇄ run_tools, agent → respond → __end__

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(SuggestQuestionsState)

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
