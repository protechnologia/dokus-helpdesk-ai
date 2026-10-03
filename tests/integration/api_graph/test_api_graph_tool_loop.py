from types import ModuleType

import pytest
from pydantic import BaseModel

from app.graph import search, suggest_questions, suggest_solution
from app.graph.fake import FAKE_SEARCH_ARGUMENTS

# Grafy z pętlą agent ⇄ run_tools.
LOOP_GRAPHS = [search, suggest_questions, suggest_solution]

# Przebieg atrapy „najpierw szukaj, potem odpowiedz".
EXPECTED_LOG = ["anonymize", "agent", "run_tools", "agent", "respond"]


def graph_name(
    graph: ModuleType,  # np. <module app.graph.search>
) -> str:
    """
    Description:
    Nazwa grafu do identyfikatora testu.

    Example args:
        graph=<module app.graph.search>

    Example result:
        "search"
    """
    return graph.__name__.split(".")[-1]


async def run_fake(
    graph: ModuleType,  # np. <module app.graph.search>
) -> BaseModel:
    """
    Description:
    Przepuszcza stan przykładowy przez atrapę grafu i oddaje stan końcowy jako model.

    Example args:
        graph=<module app.graph.search>

    Example result:
        SearchState(sources=[SourceRef(…), …], messages=[…], …)
    """
    state_type = type(graph.example_state())
    state      = state_type(**await graph.build_fake_graph().ainvoke(graph.example_state()))

    return state


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_the_loop_searches_then_answers(graph: ModuleType) -> None:
    """Atrapa agenta „najpierw szukaj, potem odpowiedz" → agent, run_tools, agent, respond: po
    wywołaniu narzędzia wiedzy przebieg wraca do agenta, po narzędziu odpowiedzi kończy."""
    state = await run_fake(graph)

    assert [entry.node for entry in state.log] == EXPECTED_LOG


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_sources_and_queries_come_from_the_run(graph: ModuleType) -> None:
    """Po przebiegu → źródła z `cite()` atrapy narzędzia w `sources`, a zapytanie agenta w jego
    turze w `messages` — z tych dwóch miejsc trasa składa wynik."""
    state = await run_fake(graph)
    query = state.messages[0].tool_calls[0]

    assert [ref.item_id for ref in state.sources] == ["90001", "90002", "90003"]
    assert (query.name, query.arguments)          == ("find_tickets_vector", FAKE_SEARCH_ARGUMENTS)
