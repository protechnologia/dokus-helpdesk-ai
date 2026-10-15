"""
Description:
Grafy aplikacji w testach: odczyt z ich pakietów w `app/agent_graphs/` (jakie grafy są, jaki mają
wynik, czy mają reguły klienta i listę źródeł) oraz składanie ich na atrapach (stan po
anonimizacji, narzędzia z listy dozwolonych, węzły pod argumentami `build_graph`, drogi między
krokami). Korzystają z niego testy spójności zestawów scenariuszy, test kontraktu grafów i test
grafów na żywym modelu.

| co                      | do czego                                                            |
|-------------------------|---------------------------------------------------------------------|
| `graph_names()`         | nazwy wszystkich grafów: katalogi w `app/agent_graphs/`             |
| `graph_modules()`       | pakiety wszystkich grafów, w kolejności nazw                        |
| `graph_module()`        | pakiet grafu po nazwie                                              |
| `graph_name()`          | nazwa grafu z jego pakietu, także jako `ids` parametryzacji         |
| `output_types()`        | typy wyniku grafu, z pola `output` jego stanu                       |
| `output_fields()`       | nazwy pól wszystkich typów wyniku grafu                             |
| `has_rules()`           | czy stan grafu ma reguły klienta                                    |
| `has_sources()`         | czy stan grafu ma listę źródeł, czyli czy graf ma narzędzia wiedzy  |
| `filled_by()`           | pola wyniku, które wypełnia graf, a nie model                       |
| `anonymized_state()`    | stan przykładowy po anonimizacji, z tekstem zastąpionym znacznikiem |
| `allowed_tools()`       | atrapy narzędzi z listy dozwolonych dla grafu                       |
| `default_tool_limits()` | limity wywołań narzędzi z konfiguracji domyślnej                    |
| `expected_edges()`      | drogi między krokami, jakie graf ma mieć przy swoim kształcie       |
| `edges_of()`            | drogi między krokami w złożonym grafie                              |
| `fake_nodes()`          | węzły, z których da się złożyć graf, pod argumentami `build_graph`  |
| `built_from()`          | graf złożony z podanych węzłów                                      |

Przykład:

    module = graph_module("suggest_questions")

    output_types(module)  -> [Proposal, ProposalNotes]
    output_fields(module) -> {"text", "internal_notes"}
    has_sources(module)   -> True

O czym pamiętać przy zmianach:

- Odczyt stoi na deklaracji stanu (`STATE`) i liście `TOOL_NAMES`, bez budowania grafu i bez
  modelu, więc helper działa w domyślnym `pytest`.
- Nowy graf to nowy katalog: `graph_names()` i `graph_modules()` znajdują go same, więc testy
  parametryzowane po nich obejmują go bez dopisywania.
"""

import importlib
import pkgutil
from types import ModuleType
from typing import get_args

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

import app.agent_graphs
from app.agent_graphs.fake import FAKE_MAX_ITERATIONS
from app.agent_nodes import Node
from app.agent_nodes.agent import FakeAgentNode
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode
from app.agent_tools import AgentTool
from app.config import Settings
from app.engine_anonymization import AnonymizedText, FakeAnonymizer
from tests._helpers.fake_tools import fake_agent_tools
from tests._helpers.graphs.constants import ANONYMIZED, GRAPHS_PACKAGE


def graph_names() -> set[str]:
    """
    Description:
    Nazwy wszystkich grafów aplikacji: katalogi z pakietem w `app/agent_graphs/`.

    Example args:
        (brak)

    Example result:
        {"gate_close", "gate_reply", "parse_ticket", "polish", "search", "suggest_handoff", …}
    """
    names = {
        module.name
        for module in pkgutil.iter_modules(app.agent_graphs.__path__)
        if module.ispkg
    }

    return names


def graph_modules() -> list[ModuleType]:
    """
    Description:
    Pakiety wszystkich grafów aplikacji, w kolejności nazw — także tych, których jeszcze nie ma:
    nowy graf to nowy katalog, więc test parametryzowany tą listą znajduje go sam.

    Example args:
        (brak)

    Example result:
        [<module app.agent_graphs.gate_close>, <module app.agent_graphs.gate_reply>, …]
    """
    return [graph_module(name) for name in sorted(graph_names())]


def graph_module(
    name: str,  # np. "suggest_questions"
) -> ModuleType:
    """
    Description:
    Pakiet grafu po nazwie jego katalogu.

    Example args:
        name="suggest_questions"

    Example result:
        <module app.agent_graphs.suggest_questions>
    """
    return importlib.import_module(f"{GRAPHS_PACKAGE}.{name}")


def graph_name(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> str:
    """
    Description:
    Nazwa grafu, czyli nazwa jego katalogu. Służy też jako `ids` parametryzacji po pakietach
    grafów, żeby nazwa testu mówiła, którego grafu dotyczy.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        "gate_close"
    """
    return graph.__name__.split(".")[-1]


def output_types(
    graph: ModuleType,  # np. <module app.agent_graphs.suggest_questions>
) -> list[type[BaseModel]]:
    """
    Description:
    Typy wyniku grafu, odczytane z pola `output` jego stanu, bez `None`, w kolejności deklaracji.

    Example args:
        graph=<module app.agent_graphs.suggest_questions>

    Example result:
        [Proposal, ProposalNotes]
    """
    annotation = graph.STATE.model_fields["output"].annotation
    types      = [arg for arg in get_args(annotation) if arg is not type(None)]

    return types


def output_fields(
    graph: ModuleType,  # np. <module app.agent_graphs.suggest_handoff>
) -> set[str]:
    """
    Description:
    Nazwy pól wszystkich typów wyniku grafu.

    Example args:
        graph=<module app.agent_graphs.suggest_handoff>

    Example result:
        {"text", "internal_notes"}
    """
    return {name for output_type in output_types(graph) for name in output_type.model_fields}


def has_rules(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_reply>
) -> bool:
    """
    Description:
    Czy stan grafu ma reguły klienta.

    Example args:
        graph=<module app.agent_graphs.gate_reply>

    Example result:
        True
    """
    return "rules" in graph.STATE.model_fields


def has_sources(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> bool:
    """
    Description:
    Czy stan grafu ma listę źródeł, czyli czy graf ma narzędzia wiedzy.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        True
    """
    return "sources" in graph.STATE.model_fields


def filled_by(
    graph: ModuleType,  # np. <module app.agent_graphs.parse_ticket>
) -> tuple[str, ...]:
    """
    Description:
    Pola wyniku, których model nie podaje, bo wypełnia je graf — dziś tylko w `parse_ticket`.

    Example args:
        graph=<module app.agent_graphs.parse_ticket>

    Example result:
        ("ticket_id", "date", "resolution_vocabulary_version")
    """
    return getattr(graph, "FILLED_BY_GRAPH", ())


def anonymized_state(
    graph: ModuleType,  # np. <module app.agent_graphs.gate_close>
) -> BaseModel:
    """
    Description:
    Przykładowy stan grafu po anonimizacji, w którym tekst zanonimizowany to znacznik
    `ANONYMIZED`: gdy znacznik jest w prompcie, a tekstu surowego nie ma, prompt wziął treść
    z `anonymized`.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        GateCloseState(input_text="Nie przychodzą…", anonymized=AnonymizedText(text="ZANON…"), …)
    """
    state = graph.example_state().model_copy(update={"anonymized": AnonymizedText(text=ANONYMIZED)})

    return state


def allowed_tools(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> list[AgentTool]:
    """
    Description:
    Atrapy narzędzi z listy dozwolonych dla grafu, wybrane z atrap wszystkich narzędzi, w ich
    kolejności.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        [FakeFindTicketsVectorTool(), FakeFindTicketsTextTool(), FakeListDocsTool(), …]
    """
    return [tool for tool in fake_agent_tools() if tool.name in graph.TOOL_NAMES]


def default_tool_limits() -> dict[str, int]:
    """
    Description:
    Limity wywołań narzędzi, jakie daje konfiguracja domyślna, bez pliku `.env`.

    Example args:
        (brak)

    Example result:
        {"find_tickets_vector": 5, "read_tickets_card": 5, "read_docs": 3, …}
    """
    return Settings(_env_file=None).tool_call_limits()


def expected_edges(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> set[tuple[str, str]]:
    """
    Description:
    Drogi między krokami, jakie graf ma mieć przy swoim kształcie. Każdy graf idzie od
    anonimizacji przez turę modelu do odpowiedzi, a z odpowiedzi może wrócić do modelu na
    poprawkę; graf z narzędziami wiedzy ma do tego pętlę między modelem a wykonaniem narzędzi.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        {("__start__", "anonymize"), ("anonymize", "agent"), ("agent", "respond"),
         ("respond", "agent"), ("respond", "__end__")}
    """
    edges = {
        ("__start__", "anonymize"),
        ("anonymize", "agent"),
        ("agent", "respond"),
        ("respond", "agent"),
        ("respond", "__end__"),
    }

    if graph.TOOL_NAMES:
        edges |= {("agent", "run_tools"), ("run_tools", "agent")}

    return edges


def edges_of(
    compiled: CompiledStateGraph,  # np. gate_close.build_fake_graph()
) -> set[tuple[str, str]]:
    """
    Description:
    Drogi między krokami w złożonym grafie, jako pary „skąd, dokąd".

    Example args:
        compiled=gate_close.build_fake_graph()

    Example result:
        {("__start__", "anonymize"), ("anonymize", "agent"), ("agent", "respond"), …}
    """
    return {(edge.source, edge.target) for edge in compiled.get_graph().edges}


async def fake_nodes(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> dict[str, Node]:
    """
    Description:
    Węzły, z których da się złożyć dany graf, pod nazwami argumentów `build_graph`: anonimizacja
    na atrapie anonimizatora i atrapy pozostałych, w grafie z narzędziami wiedzy także atrapa
    `run_tools`. Wynik dla atrapy odpowiedzi pochodzi z przebiegu atrapy grafu, żeby helper nie
    trzymał listy typów wyników.

    Example args:
        graph=<module app.agent_graphs.gate_close>

    Example result:
        {"anonymize": AnonymizeNode(…), "agent": FakeAgentNode(), "respond": FakeRespondNode(…)}
    """
    final = graph.STATE(**await graph.build_fake_graph().ainvoke(graph.example_state()))

    nodes: dict[str, Node] = {
        "anonymize": AnonymizeNode(FakeAnonymizer()),
        "agent":     FakeAgentNode(),
        "respond":   FakeRespondNode(final.output),
    }

    if graph.TOOL_NAMES:
        nodes["run_tools"] = FakeRunToolsNode()

    return nodes


def built_from(
    graph: ModuleType,       # np. <module app.agent_graphs.search>
    nodes: dict[str, Node],  # argument `build_graph` -> węzeł, np. {"agent": FakeAgentNode(), …}
) -> CompiledStateGraph:
    """
    Description:
    Składa graf z podanych węzłów, każdy pod wskazanym argumentem `build_graph`. Graf
    z narzędziami wiedzy dostaje do tego limit tur.

    Example args:
        graph=<module app.agent_graphs.gate_close>
        nodes={"anonymize": AnonymizeNode(…), "agent": FakeAgentNode(),
               "respond": FakeRespondNode(…)}

    Example result:
        CompiledStateGraph: anonymize → agent → respond

    Raises:
        ValueError: dwa węzły o tej samej nazwie
    """
    if graph.TOOL_NAMES:
        return graph.build_graph(**nodes, max_iterations=FAKE_MAX_ITERATIONS)

    return graph.build_graph(**nodes)
