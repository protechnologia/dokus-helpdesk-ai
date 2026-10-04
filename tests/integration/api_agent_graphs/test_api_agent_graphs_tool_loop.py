from types import ModuleType

import pytest
from pydantic import BaseModel

from app.agent_graphs import search, suggest_questions, suggest_solution
from app.agent_graphs.fake import FAKE_READ_ARGUMENTS, FAKE_SEARCH_ARGUMENTS

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
