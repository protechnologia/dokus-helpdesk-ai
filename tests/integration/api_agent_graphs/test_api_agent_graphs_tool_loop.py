import json
from types import ModuleType

import pytest
from pydantic import BaseModel

from app.agent_graphs import gate_close, search, suggest_questions, suggest_solution
from app.agent_graphs.factory import build_function_graph
from app.agent_graphs.fake import (
    FAKE_MAX_ITERATIONS,
    FAKE_READ_ARGUMENTS,
    FAKE_SEARCH_ARGUMENTS,
)
from app.agent_nodes.agent import FakeAgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import FakeRunToolsNode
from app.engine_anonymization import FakeAnonymizer
from app.engine_llm import LLMUsage

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
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy (wyszukiwanie, propozycja pytań
    i propozycja rozwiązania) przebieg „szukaj, czytaj, odpowiedz" idzie właściwą drogą: po
    każdym wywołaniu narzędzia wraca do modelu, a po wywołaniu narzędzia odpowiedzi się kończy.

    Wyłapuje źle poprowadzoną pętlę: graf, który po wykonaniu narzędzia nie wraca do modelu,
    kończy przed odczytem albo kręci się dalej po odpowiedzi."""
    state = await run_fake(graph)

    assert [entry.node for entry in state.log] == EXPECTED_LOG


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_sources_and_queries_come_from_the_run(graph: ModuleType) -> None:
    """Sprawdza, czy po przebiegu stan grafu niesie to, z czego trasa składa wynik: listę źródeł
    z trzema przeczytanymi zgłoszeniami (90001, 90002, 90003) oraz zapis tego, co model
    wywołał — najpierw wyszukiwanie, potem odczyt kart — razem z argumentami.

    Wyłapuje stan, w którym źródła albo wywołania giną po drodze: odpowiedź wróciłaby wtedy bez
    listy źródeł albo bez informacji, o co agent pytał."""
    state = await run_fake(graph)
    calls = [message.tool_calls[0] for message in state.messages if message.tool_calls]

    assert [ref.item_id for ref in state.sources] == ["90001", "90002", "90003"]
    assert (calls[0].name, calls[0].arguments)    == ("find_tickets_vector", FAKE_SEARCH_ARGUMENTS)
    assert (calls[1].name, calls[1].arguments)    == ("read_tickets_card", FAKE_READ_ARGUMENTS)


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_sources_appear_only_after_the_read(graph: ModuleType) -> None:
    """Sprawdza, czy w przebiegu na atrapach źródła dochodzą dopiero po odczycie: po wyszukaniu
    zgłoszeń krok wykonujący narzędzia zapisuje zero źródeł, a po odczycie kart trzy.

    Wyłapuje przebieg, w którym na listę źródeł trafia już to, co model tylko znalazł: odpowiedź
    powoływałaby się wtedy na zgłoszenia, których treści model nie przeczytał."""
    state = await run_fake(graph)
    tools = [entry.message for entry in state.log if entry.node == "run_tools"]

    assert tools == [
        "wywołania: find_tickets_vector; źródła: 0",
        "wywołania: read_tickets_card; źródła: 3",
    ]


async def test_a_call_over_the_limit_gets_an_error_and_the_loop_goes_on() -> None:
    """Sprawdza, czy przy limicie dwóch wywołań trzecie wyszukiwanie zgłoszeń dostaje w miejscu
    wyniku komunikat o błędzie, a przebieg idzie dalej i kończy się odpowiedzią. Dwa pierwsze
    wyszukiwania dostają zwykły wynik, a w dzienniku przebiegu zostaje ślad jednego wywołania
    ponad limit.

    Wyłapuje limit, który nie działa (model szukałby bez ograniczeń) albo działa za ostro
    i przerywa całe żądanie, zamiast powiedzieć modelowi, żeby odpowiedział z tego, co ma."""
    agent = FakeAgentNode([
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_2"),
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_3"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_4"),
    ])
    graph = search.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = agent,
        run_tools      = FakeRunToolsNode(
            result_text = '{"tickets": []}',
            limits      = {"find_tickets_vector": 2},
        ),
        respond        = FakeRespondNode(search.SearchDone()),
        max_iterations = FAKE_MAX_ITERATIONS,
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
    """Sprawdza, czy fabryka grafów przekazuje grafowi z narzędziami ustawienia ze zmiennych
    środowiskowych: limit wywołań narzędzia (tu 7 dla `read_docs`), limit tur modelu (tu 4)
    i limit dla każdego narzędzia tego grafu. Graf bez narzędzi, tu bramka zamknięcia, buduje
    się bez tych ustawień.

    Wyłapuje fabrykę, która gubi konfigurację: limity wpisane w `.env` nie miałyby wtedy żadnego
    skutku, a nic by tego nie zasygnalizowało, bo graf działa także bez limitów."""
    monkeypatch.setenv("AGENT_MAX_CALLS_READ_DOCS", "7")
    monkeypatch.setenv("AGENT_MAX_ITERATIONS", "4")

    received: dict = {}

    def fake_build(**kwargs: object) -> str:
        received.update(kwargs)

        return "graf"

    monkeypatch.setattr(search, "build_fake_graph", fake_build)

    assert build_function_graph(search) == "graf"
    assert received["limits"]["read_docs"] == 7
    assert received["max_iterations"]      == 4
    assert set(received["limits"]) >= set(search.TOOL_NAMES)
    assert build_function_graph(gate_close) is not None


async def test_the_cost_of_every_model_turn_adds_up_in_the_state() -> None:
    """Sprawdza, czy zużycie modelu z kolejnych tur sumuje się w stanie grafu: po trzech turach,
    każda za 0,02 USD, stan pokazuje trzy wywołania, sumę tokenów każdego rodzaju i koszt
    0,06 USD, a liczba wywołań zgadza się z liczbą tur.

    Wyłapuje stan, który zamiast sumować zapamiętuje tylko ostatnią turę albo gubi któryś
    licznik: odpowiedź podawałaby wtedy zaniżony koszt sprawy."""
    turn_usage = LLMUsage(
        calls             = 1,
        prompt_tokens     = 5000,
        completion_tokens = 100,
        cache_read_tokens = 400,
        cost_usd          = 0.02,
    )
    agent = FakeAgentNode(
        [
            tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
            tool_call_turn("read_tickets_card", FAKE_READ_ARGUMENTS, call_id="call_2"),
            tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
        ],
        usage = turn_usage,
    )
    graph = search.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = agent,
        run_tools      = FakeRunToolsNode(result_text="{}"),
        respond        = FakeRespondNode(search.SearchDone()),
        max_iterations = FAKE_MAX_ITERATIONS,
    )

    state = search.STATE(**await graph.ainvoke(search.example_state()))

    assert state.usage.calls             == 3
    assert state.usage.prompt_tokens     == 15000
    assert state.usage.completion_tokens == 300
    assert state.usage.cache_read_tokens == 1200
    assert state.usage.cost_usd          == pytest.approx(0.06)
    assert state.usage.calls             == state.iterations


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=graph_name)
async def test_a_fake_run_counts_model_calls_and_costs_nothing(graph: ModuleType) -> None:
    """Sprawdza, czy przebieg na atrapach liczy wywołania modelu (trzy tury to trzy wywołania),
    a tokeny i koszt zostawia na zerze: atrapa niczego nie wysyła, więc nic nie kosztuje.

    Wyłapuje atrapę, która nie liczy wywołań albo zmyśla tokeny i koszt: zero w odpowiedzi ma
    znaczyć, że naprawdę nic nie wysłano, a nie że zabrakło danych."""
    state = await run_fake(graph)

    assert state.usage.calls         == 3
    assert state.usage.prompt_tokens == 0
    assert state.usage.cost_usd      == 0.0
