from langgraph.graph.state import CompiledStateGraph

from app.anonymization import FakeAnonymizer
from app.graph.polish.graph import build_graph
from app.graph.polish.models import PolishedText
from app.graph.polish.respond_tool import RESPOND_TOOL_NAME
from app.graph.polish.state import PolishState
from app.nodes.agent import FakeAgentNode, tool_call_turn
from app.nodes.anonymize import AnonymizeNode
from app.nodes.respond import FakeRespondNode

# Tekst atrapy, gdy nikt nie podał własnego — stały, żeby test, który przypadkiem na nim polega,
# padł głośno.
DEFAULT_TEXT = PolishedText(text="fake-polish-text")


def example_state() -> PolishState:
    """
    Description:
    Przykładowy stan wejściowy grafu — do testów i atrap tras. Dane zmyślone.

    Example args:
        (brak)

    Example result:
        PolishState(input_text="przesylki juz ida, kolejka stala…", rules=["Zwracaj się…", …])
    """
    state = PolishState(
        input_text = "przesylki juz ida, kolejka stala, zrestartowalem i jest ok",
        rules      = ["Zwracaj się do klienta per Państwo.", "Bez potocznego słownictwa."],
    )

    return state


def build_fake_graph(
    polished: PolishedText = DEFAULT_TEXT,  # np. PolishedText(text="Dzień dobry, przesyłki…")
) -> CompiledStateGraph:
    """
    Description:
    Ten sam graf co `build_graph`, złożony z atrap — do testów tras i CLI. Agent wywołuje
    `respond_polish` z tekstem w argumentach, a `respond` oddaje ten tekst.

    Graf jest jednorazowy: `FakeAgentNode` ma jedną turę. Na każde wywołanie buduj nowy.

    Example args:
        polished=PolishedText(text="Dzień dobry, przesyłki już docierają…")

    Example result:
        CompiledStateGraph, który na dowolne notatki oddaje `output` = podany tekst
    """
    answer = tool_call_turn(RESPOND_TOOL_NAME, polished.model_dump())

    graph = build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = FakeAgentNode([answer]),
        respond   = FakeRespondNode(polished),
    )

    return graph
