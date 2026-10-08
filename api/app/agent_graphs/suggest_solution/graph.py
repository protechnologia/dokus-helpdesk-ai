from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs.base import (
    route_after_agent,
    route_after_respond,
    tool_definitions,
)
from app.agent_graphs.suggest_solution.respond_tool import RESPOND_TOOL_NAME, respond_tool
from app.agent_graphs.suggest_solution.state import SuggestSolutionState
from app.agent_nodes import Node
from app.agent_nodes.respond import RespondNode
from app.agent_tools import AgentTool
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes
from app.core_util.markdown import read_document
from app.engine_llm import ToolDefinition

GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

TICKET_PLACEHOLDER = "{{ticket}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = SuggestSolutionState

# Narzędzia dozwolone w tym grafie; opis każdego dla modelu leży w katalogu narzędzia.
TOOL_NAMES: tuple[str, ...] = (
    "find_tickets_vector",  # numery zgłoszeń po znaczeniu
    "find_tickets_text",    # numery zgłoszeń po dosłownym brzmieniu
    "read_tickets_card",    # karty zgłoszeń po numerach — cytuje
    "read_tickets_thread",  # oryginalne wątki po numerach — cytuje
    "list_docs",            # spis treści dokumentacji
    "find_docs_vector",     # sekcje dokumentacji po znaczeniu
    "find_docs_text",       # sekcje dokumentacji po dosłownym brzmieniu
    "read_docs",            # treść sekcji po identyfikatorach — cytuje
    "quote_code",           # fragment kodu aplikacji — cytuje tylko wskazaną przyczynę
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
    tools:  Sequence[AgentTool],  # np. [FakeFindTicketsVectorTool(), FakeReadDocsTool()]
    limits: Mapping[str, int],    # np. {"find_tickets_vector": 3}
) -> list[ToolDefinition]:
    """
    Description: Narzędzia, które model widzi w tym grafie: podane narzędzia (z listy dozwolonych)
    i na końcu `respond_suggest_solution`. Narzędzi dokumentacji może nie być — instancja bez
    dokumentacji ich nie rejestruje.

    Example args:
        tools=[FakeFindTicketsVectorTool(), FakeFindDocsVectorTool()]
        limits={"find_tickets_vector": 3, "find_docs_vector": 3}

    Example result:
        [ToolDefinition(name="find_tickets_vector", …), ToolDefinition(name="read_tickets_card", …),
         ToolDefinition(name="respond_suggest_solution", …)]

    Raises:
        ValueError: narzędzie spoza listy dozwolonych albo bez limitu wywołań
    """
    definitions = tool_definitions(tools, TOOL_NAMES, limits) + [respond_tool()]

    return definitions


def without_sources(
    proposal: Proposal,  # np. Proposal(text="Prosimy o restart usługi.", internal_notes="…")
) -> ProposalNotes:
    """
    Description:
    To, co z propozycji zostaje, gdy agent nie odczytał żadnego źródła: same uwagi dla
    wdrożeniowca. Treść dla klienta odpada, bo bez źródeł byłaby napisana „z głowy" (zasada 9),
    a uwagi mówią wdrożeniowcowi, czego agent szukał i co wykluczył. Węzeł `respond` woła tę
    funkcję po przyjęciu odpowiedzi.

    Example args:
        proposal=Proposal(text="Prosimy o restart usługi.",
                          internal_notes="Szukałem po komunikacie — brak podobnych spraw.")

    Example result:
        ProposalNotes(internal_notes="Szukałem po komunikacie — brak podobnych spraw.")
    """
    return ProposalNotes(internal_notes=proposal.internal_notes)


def respond_node() -> RespondNode:
    """
    Description:
    Węzeł odpowiedzi tego grafu: waliduje argumenty `respond_suggest_solution` do `Proposal`
    i egzekwuje `REQUIRES_HITS`: gdy agent nie odczytał żadnego źródła, treść dla klienta odpada,
    cokolwiek model napisał, a zostają same uwagi (`without_sources()`, zasada 9).

    Example args:
        (brak)

    Example result:
        RespondNode czytający wywołanie `respond_suggest_solution` jako `Proposal`, a bez źródeł
        zapisujący `ProposalNotes`
    """
    node = RespondNode(
        respond_tool_name = RESPOND_TOOL_NAME,
        output_model      = Proposal,
        requires_sources  = REQUIRES_HITS,
        without_sources   = without_sources,
    )

    return node


def build_graph(
    anonymize:      Node,  # np. AnonymizeNode(FakeAnonymizer())
    agent:          Node,  # np. FakeAgentNode([tool_call_turn("find_tickets_vector", …), …])
    run_tools:      Node,  # np. FakeRunToolsNode(sources=[…])
    respond:        Node,  # np. FakeRespondNode(Proposal(text="…", internal_notes="…"))
    max_iterations: int,   # np. 20 — limit tur modelu z `AGENT_MAX_ITERATIONS`
) -> CompiledStateGraph:
    """
    Description:
    Składa graf wariantu z gotowych węzłów: anonimizacja → pętla agent ⇄ run_tools → respond. Po
    każdej turze modelu `route_after_agent` decyduje: narzędzia wiedzy → kolejny obieg,
    `respond_suggest_solution` albo sam tekst → koniec. Po `max_iterations` turach modelu
    narzędzia nie są już wykonywane i przebieg też idzie do `respond`. Krawędzie idą po nazwach
    węzłów.

    Po `respond` przebieg się kończy, chyba że węzeł odesłał odpowiedź modelowi do poprawki —
    wtedy model dostaje jeszcze jedną turę (`route_after_respond`).

    Example args:
        anonymize=AnonymizeNode(FakeAnonymizer())
        agent=FakeAgentNode([…])
        run_tools=FakeRunToolsNode(sources=[…])
        respond=FakeRespondNode(Proposal(text="…", internal_notes="…"))
        max_iterations=20

    Example result:
        CompiledStateGraph: __start__ → anonymize → agent ⇄ run_tools, agent → respond → __end__,
        respond → agent przy poprawce

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    graph = StateGraph(SuggestSolutionState)

    for node in (anonymize, agent, run_tools, respond):
        graph.add_node(node.name, node.run)

    route = partial(
        route_after_agent,                      # wspólne rozgałęzienie grafów z pętlą
        respond_tool_name = RESPOND_TOOL_NAME,  # czym model odpowiada w tym grafie
        max_iterations    = max_iterations,     # po tylu turach narzędzia nie są już wykonywane
    )

    graph.add_edge(START, "anonymize")
    graph.add_edge("anonymize", "agent")
    graph.add_conditional_edges(
        "agent",                   # po każdej turze modelu
        route,                     # decyduje to, co model wywołał, i limit tur
        ["run_tools", "respond"],  # możliwe cele
    )
    graph.add_edge("run_tools", "agent")
    graph.add_conditional_edges(
        "respond",            # po odczytaniu odpowiedzi modelu
        route_after_respond,  # odpowiedź odesłana do poprawki → jeszcze jedna tura modelu
        ["agent", END],       # możliwe cele
    )

    return graph.compile()
