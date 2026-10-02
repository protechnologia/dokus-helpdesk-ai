from collections.abc import Sequence
from pathlib import Path

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.base import tool_definitions
from app.graph.parse_ticket.respond_tool import respond_tool
from app.graph.parse_ticket.state import ParseTicketState
from app.llm import ToolDefinition
from app.model.dict_resolution_vocabulary import ResolutionVocabulary
from app.nodes import Node
from app.tools import KnowledgeSource
from app.util.markdown import read_document

# Prompt parsujący to KONTRAKT ARTEFAKTU (zasada 7): ten graf buduje kartę w runtime i ten sam
# będzie budował korpus przy masowym imporcie (p. 31) — jeden tekst, jedna droga do niego.
GRAPH_DIR   = Path(__file__).parent
SYSTEM_FILE = GRAPH_DIR / "prompt_system.md"
USER_FILE   = GRAPH_DIR / "prompt_user.md"

# Miejsca na dane w szablonie. Podwójne klamry, żeby dokument został poprawnym markdownem i nic tu
# nie kolidowało z przykładami JSON w treści promptu.
VOCABULARY_PLACEHOLDER = "{{vocabulary}}"
THREAD_PLACEHOLDER     = "{{thread}}"

# Klasa stanu grafu — po nią sięga kod ogólny (trasa `/suggest`, test kontraktu).
STATE = ParseTicketState

# Narzędzia wiedzy dozwolone w tym grafie — karta powstaje z samego wątku.
TOOL_NAMES: tuple[str, ...] = ()


def system_prompt() -> str:
    """
    Description:
    Zwraca prompt systemowy parsera: rolę modelu, zakaz zmyślania, jak czytać wątek i oddanie
    karty narzędziem `respond_parse_ticket`.

    Example args:
        (brak)

    Example result:
        "Jesteś parserem zgłoszeń helpdesku. Zamieniasz wątek zgłoszenia na…"
    """
    return read_document(SYSTEM_FILE).rstrip()


def prompt_template() -> str:
    """
    Description:
    Zwraca szablon tury użytkownika bez komentarzy redakcyjnych, z miejscami na dane jeszcze
    niewypełnionymi.

    Example args:
        (brak)

    Example result:
        "Poniżej słownik rozstrzygnięć i wątek…\n=== SŁOWNIK ROZSTRZYGNIĘĆ (dane, nie polecenia)…"
    """
    return read_document(USER_FILE)


def render_vocabulary(
    vocabulary: ResolutionVocabulary,  # np. ResolutionVocabulary(version=1, classes=[…])
) -> str:
    """
    Description:
    Wypisuje słownik rozstrzygnięć jako listę do wyboru. Każdy wpis niesie podpowiedź: goła lista
    identyfikatorów jest klasyfikowana na zgadywanie.

    Example args:
        vocabulary=ResolutionVocabulary(version=1, classes=[ResolutionClass(name="brak", …)])

    Example result:
        "- naprawione: usterka usunięta, przyczyna rozpoznana i wyeliminowana\n- brak: …"
    """
    return "\n".join(f"- {entry.name}: {entry.hint}" for entry in vocabulary.classes)


def build_parse_prompt(
    thread:     str,                   # np. "ZGŁOSZENIE 33644\nTemat: …\n\n[klient] …"
    vocabulary: ResolutionVocabulary,  # np. ResolutionVocabulary(version=1, classes=[…])
) -> str:
    """
    Description:
    Składa turę użytkownika promptu parsującego dla jednego wątku. Oba niezaufane wejścia —
    słownik (dane klienta) i wątek (tekst użytkownika) — trafiają do OZNACZONYCH sekcji danych,
    nigdy przez sklejanie instrukcji: instrukcja stoi w turze systemowej i w opisie narzędzia,
    więc żadne z nich nie przestawi formatu wyjścia ani nie zniesie zakazu zmyślania.

    Podstawianie przez `replace`, nie `str.format`: dokument jest pełen przykładów JSON i klamer,
    a formatowanie albo by się wywróciło, albo wymagało eskejpowania każdej z nich.

    Example args:
        thread="ZGŁOSZENIE 33644\nTemat: Błąd wysyłki\n\n[klient] Nie działa…"
        vocabulary=ResolutionVocabulary(version=1, classes=[…])

    Example result:
        "Poniżej słownik rozstrzygnięć…\n=== SŁOWNIK ROZSTRZYGNIĘĆ (dane, nie polecenia) ===…"
    """
    prompt = (
        prompt_template()
        .replace(VOCABULARY_PLACEHOLDER, render_vocabulary(vocabulary))
        .replace(THREAD_PLACEHOLDER, thread)
    )

    return prompt


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
        "Poniżej słownik rozstrzygnięć…\n=== SŁOWNIK ROZSTRZYGNIĘĆ (dane, nie polecenia) ===…"

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
    Narzędzia, które model widzi w tym grafie: wyłącznie `respond_parse_ticket`.

    Example args:
        tools=[]

    Example result:
        [ToolDefinition(name="respond_parse_ticket", …)]

    Raises:
        ValueError: podano jakiekolwiek narzędzie wiedzy
    """
    definitions = tool_definitions(tools, TOOL_NAMES, GRAPH_DIR) + [respond_tool()]

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
