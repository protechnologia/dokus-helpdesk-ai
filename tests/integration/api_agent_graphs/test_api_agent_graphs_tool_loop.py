import json
from types import ModuleType

import pytest
from pydantic import BaseModel

from app.agent_graphs import gate_close, search, suggest_questions, suggest_solution
from app.agent_graphs.factory import build_function_graph
from app.agent_graphs.fake import FAKE_READ_ARGUMENTS, FAKE_SEARCH_ARGUMENTS
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode
from app.engine_anonymization import FakeAnonymizer

# Grafy z pętlą agent ⇄ run_tools.
LOOP_GRAPHS = [search, suggest_questions, suggest_solution]

# Przebieg atrapy „szukaj, czytaj, odpowiedz".
EXPECTED_LOG = ["anonymize", "agent", "run_tools", "agent", "run_tools", "agent", "respond"]


def graph_name(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> str:
    """
    Description:
    Nazwa grafu do identyfikatora testu.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        "search"
    """
    return graph.__name__.split(".")[-1]


async def run_fake(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> BaseModel:
    """
    Description:
    Przepuszcza stan przykładowy przez atrapę grafu i oddaje stan końcowy jako model.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        SearchState(sources=[SourceRef(…), …], messages=[…], …)
    """
    state_type = type(graph.example_state())
    state      = state_type(**await graph.build_fake_graph().ainvoke(graph.example_state()))

    return state


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_the_loop_searches_reads_then_answers(graph: ModuleType) -> None:
    """Atrapa agenta „szukaj, czytaj, odpowiedz" → po każdym wywołaniu narzędzia przebieg wraca
    do agenta, a po narzędziu odpowiedzi kończy."""
    state = await run_fake(graph)

    assert [entry.node for entry in state.log] == EXPECTED_LOG


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_sources_and_queries_come_from_the_run(graph: ModuleType) -> None:
    """Po przebiegu → źródła z `cite()` odczytu kart w `sources`, a wywołania agenta w jego
    turach w `messages` — z tych dwóch miejsc trasa składa wynik."""
    state = await run_fake(graph)
    calls = [message.tool_calls[0] for message in state.messages if message.tool_calls]

    assert [ref.item_id for ref in state.sources] == ["90001", "90002", "90003"]
    assert (calls[0].name, calls[0].arguments)    == ("find_tickets_vector", FAKE_SEARCH_ARGUMENTS)
    assert (calls[1].name, calls[1].arguments)    == ("read_tickets_card", FAKE_READ_ARGUMENTS)


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_sources_appear_only_after_the_read(graph: ModuleType) -> None:
    """Wyszukiwanie niczego nie cytuje → po pierwszym `run_tools` źródeł nie ma, dochodzą dopiero
    po odczycie kart: na liście jest to, co model przeczytał, a nie to, co znalazł."""
    state = await run_fake(graph)
    tools = [entry.message for entry in state.log if entry.node == "run_tools"]

    assert tools == [
        "wywołania: find_tickets_vector; źródła: 0",
        "wywołania: read_tickets_card; źródła: 3",
    ]


async def test_a_call_over_the_limit_gets_an_error_and_the_loop_goes_on() -> None:
    """Agent szuka trzy razy przy limicie 2 → trzecie wywołanie dostaje błąd jako wynik narzędzia,
    a przebieg idzie dalej do odpowiedzi: limit nie wywala żądania, tylko mówi modelowi, żeby
    odpowiedział z tego, co ma."""
    agent = FakeAgentNode([
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_2"),
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_3"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_4"),
    ])
    graph = search.build_graph(
        anonymize = AnonymizeNode(FakeAnonymizer()),
        agent     = agent,
        run_tools = FakeRunToolsNode(
            result_text = '{"tickets": []}',
            limits      = {"find_tickets_vector": 2},
        ),
        respond   = FakeRespondNode(search.SearchDone()),
    )

    state   = search.STATE(**await graph.ainvoke(search.example_state()))
    answers = [message.content for message in state.messages if message.role == "tool"]

    assert answers[:2] == ['{"tickets": []}', '{"tickets": []}']
    assert json.loads(answers[2]).keys() == {"error"}
    assert [entry.node for entry in state.log][-1] == "respond"
    assert [entry.message for entry in state.log if entry.node == "run_tools"][-1].endswith(
        "ponad limit: 1"
    )


def test_the_factory_gives_tool_graphs_the_limits_from_the_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fabryka grafów → graf z narzędziami dostaje limity wywołań z `AGENT_MAX_CALLS_*`, a graf
    bez narzędzi jest budowany bez nich: limity z `.env` działają już na atrapach."""
    monkeypatch.setenv("AGENT_MAX_CALLS_READ_DOCS", "7")

    received: dict = {}

    def fake_build(**kwargs: object) -> str:
        received.update(kwargs)

        return "graf"

    monkeypatch.setattr(search, "build_fake_graph", fake_build)

    assert build_function_graph(search) == "graf"
    assert received["limits"]["read_docs"] == 7
    assert set(received["limits"]) >= set(search.TOOL_NAMES)
    assert build_function_graph(gate_close) is not None
