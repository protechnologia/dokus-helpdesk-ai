import json
from collections.abc import Mapping, Sequence
from types import ModuleType

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.agent_graphs import run_graph, search, suggest_questions, suggest_solution
from app.agent_graphs.fake import FAKE_MAX_ITERATIONS, FAKE_READ_ARGUMENTS, FAKE_SEARCH_ARGUMENTS
from app.agent_nodes.agent import AgentNode, tool_call_turn
from app.agent_nodes.anonymize import AnonymizeNode
from app.agent_nodes.respond import FakeRespondNode
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools import AgentTool
from app.agent_tools.base import is_error_json
from app.agent_tools.code.fake_code import ERRORS_PATH, GENERATOR_PATH
from app.config import Settings
from app.engine_anonymization import FakeAnonymizer
from app.engine_embedding import EmbeddingError
from app.engine_llm import ChatMessage, FakeLLMClient, ToolCall
from tests.helpers_agent_tools import fake_agent_tools, find_tickets_vector_with_dead_embedder

# Prawdziwy węzeł `run_tools` wpięty w grafy z pętlą i uruchomiony przez LangGraph, razem
# z prawdziwym węzłem agenta. Model to atrapa, która oddaje zaplanowane tury, narzędzia to atrapy
# na zmyślonym materiale, a odpowiedź ustawia atrapa `respond`. Te testy sprawdzają to, czego nie
# widać w teście samego węzła: czy wynik narzędzia wraca do modelu w następnej turze, czy źródła
# z kolejnych tur łączą się w stanie grafu i czy po błędzie pętla idzie dalej.

# Grafy z pętlą agent ⇄ run_tools.
LOOP_GRAPHS = [search, suggest_questions, suggest_solution]

# Limity wywołań narzędzi, jakie daje konfiguracja domyślna.
LIMITS = Settings(_env_file=None).tool_call_limits()


def name_of(
    graph: ModuleType,  # np. <module app.agent_graphs.search>
) -> str:
    """
    Description:
    Nazwa grafu = nazwa jego katalogu.

    Example args:
        graph=<module app.agent_graphs.search>

    Example result:
        "search"
    """
    return graph.__name__.split(".")[-1]


async def loop_graph(
    graph:  ModuleType,                         # np. <module app.agent_graphs.search>
    llm:    FakeLLMClient,                      # np. FakeLLMClient(turns=[…])
    tools:  Sequence[AgentTool] | None = None,  # np. [FakeReadTicketsThreadTool()]
    limits: Mapping[str, int] = LIMITS,         # np. {**LIMITS, "read_tickets_thread": 1}
) -> CompiledStateGraph:
    """
    Description:
    Graf z pętlą złożony tak, jak zrobi to fabryka: węzły właściwe `agent` i `run_tools` dostają
    te same narzędzia i limity, a prompt bierze się z pakietu grafu. Tylko `respond` to atrapa —
    oddaje wynik w typie grafu, wzięty z przebiegu jego atrapy.

    Example args:
        graph=<module app.agent_graphs.search>
        llm=FakeLLMClient(turns=[tool_call_turn("respond_search", {})])
        tools=None
        limits=LIMITS

    Example result:
        CompiledStateGraph: anonymize → agent ⇄ run_tools (oba właściwe) → respond
    """
    tools  = list(tools) if tools is not None else fake_agent_tools()
    output = (await run_graph(graph.build_fake_graph(), graph.example_state())).output

    compiled = graph.build_graph(
        anonymize      = AnonymizeNode(FakeAnonymizer()),
        agent          = AgentNode(
            llm           = llm,
            system_prompt = graph.system_prompt(),
            user_prompt   = graph.user_prompt,
            tools         = graph.model_tools(tools, limits),
        ),
        run_tools      = RunToolsNode(tools, limits),
        respond        = FakeRespondNode(output),
        max_iterations = FAKE_MAX_ITERATIONS,
    )

    return compiled


def tool_results(
    messages: Sequence[ChatMessage],  # np. rozmowa ze stanu końcowego grafu
) -> list[str]:
    """
    Description:
    Teksty, które model dostał od narzędzi, w kolejności wywołań.

    Example args:
        messages=[ChatMessage(role="user", …), ChatMessage(role="assistant", …),
                  ChatMessage(role="tool", call_id="call_1", content='{"tickets": […]}')]

    Example result:
        ['{"tickets": […]}']
    """
    return [message.content for message in messages if message.role == "tool"]


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=name_of)
async def test_the_sources_of_the_run_are_what_the_tools_read(graph: ModuleType) -> None:
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy przebieg „szukaj, czytaj, odpowiedz" na
    prawdziwym węźle narzędzi kończy się trzema źródłami, czyli kartami trzech przeczytanych
    zgłoszeń (90001, 90002, 90003), a samo wyszukanie tych numerów nie dokłada żadnego.

    Wyłapuje graf, w którym źródła z węzła narzędzi nie docierają do stanu końcowego albo trafia
    do nich to, co model tylko znalazł: odpowiedź wróciłaby bez listy źródeł albo z listą
    materiału, którego nikt nie przeczytał."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("read_tickets_card", FAKE_READ_ARGUMENTS, call_id="call_2"),
        tool_call_turn(graph.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final = await run_graph(await loop_graph(graph, llm), graph.example_state())
    tools = [entry.message for entry in final.log if entry.node == "run_tools"]

    assert [ref.key for ref in final.sources] == ["tickets:90001", "tickets:90002", "tickets:90003"]
    assert tools == [
        "wywołania: find_tickets_vector; źródła: 0",
        "wywołania: read_tickets_card; źródła: 3",
    ]
    assert final.output is not None


async def test_the_model_reads_the_tool_result_in_its_next_turn() -> None:
    """Sprawdza, czy wynik narzędzia wraca do modelu w następnej turze: po wyszukaniu ostatnią
    wiadomością, jaką model dostaje, są numery znalezionych zgłoszeń, a po odczycie — karty tych
    zgłoszeń, każda odpowiedź z identyfikatorem swojego wywołania.

    Wyłapuje graf, w którym wynik z węzła narzędzi nie trafia do rozmowy albo trafia pod cudzym
    identyfikatorem: model nie widziałby, co znalazł, i szukałby tego samego w kółko."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn("read_tickets_card", FAKE_READ_ARGUMENTS, call_id="call_2"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    await run_graph(await loop_graph(search, llm), search.example_state())

    found = llm.turn_calls[1].messages[-1]
    cards = llm.turn_calls[2].messages[-1]

    assert (found.role, found.call_id) == ("tool", "call_1")
    assert (cards.role, cards.call_id) == ("tool", "call_2")
    assert [ticket["ticket_id"] for ticket in json.loads(found.content)["tickets"]] == [
        "90001", "90002", "90003",
    ]
    assert [card["ticket_id"] for card in json.loads(cards.content)["cards"]] == [
        "90001", "90002", "90003",
    ]


async def test_a_ticket_read_twice_is_one_source() -> None:
    """Sprawdza, czy zgłoszenie odczytane w jednej turze jako karta, a w następnej jako wątek, stoi
    na liście źródeł raz, z tytułem z pierwszego odczytu, czyli z karty.

    Wyłapuje graf, który skleja źródła z kolejnych tur bez usuwania powtórzeń: to samo zgłoszenie
    stałoby na liście dwa razy, pod dwoma tytułami."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]}, call_id="call_1"),
        tool_call_turn("read_tickets_thread", {"ticket_id": "90001"}, call_id="call_2"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final = await run_graph(await loop_graph(search, llm), search.example_state())

    assert [ref.key for ref in final.sources]   == ["tickets:90001"]
    assert [ref.title for ref in final.sources] == ["Nie przychodzą przesyłki z e-Doręczeń"]


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=name_of)
async def test_of_the_quoted_code_only_the_cause_is_a_source(graph: ModuleType) -> None:
    """Sprawdza, czy w każdym grafie z narzędziami wiedzy z dwóch cytowań kodu zgłoszonych w jednej
    turze — przyczyny i miejsca wykluczonego — na listę źródeł trafia tylko przyczyna, z kluczem
    ze ścieżki i zakresu linii. Model dostaje potwierdzenie obu cytowań.

    Wyłapuje graf, w którym źródłem staje się też miejsce wykluczone albo cytowanie w ogóle nie
    dociera do listy źródeł: odpowiedź powoływałaby się na kod, który model odrzucił, albo
    wracała bez źródła mimo wskazanej przyczyny."""
    cause    = {"path": GENERATOR_PATH, "from_line": 8, "to_line": 10, "role": "cause"}
    excluded = {"path": ERRORS_PATH, "from_line": 7, "to_line": 7, "role": "excluded"}
    quotes   = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="call_1", name="quote_code", arguments=cause),
            ToolCall(call_id="call_2", name="quote_code", arguments=excluded),
        ],
    )
    llm = FakeLLMClient(turns=[
        quotes,
        tool_call_turn(graph.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final   = await run_graph(await loop_graph(graph, llm), graph.example_state())
    results = [json.loads(text) for text in tool_results(final.messages)]

    assert [ref.key for ref in final.sources] == [f"code:{GENERATOR_PATH}:8-10"]
    assert [result["role"] for result in results] == ["cause", "excluded"]
    assert [entry.message for entry in final.log if entry.node == "run_tools"] == [
        "wywołania: quote_code, quote_code; źródła: 1",
    ]


@pytest.mark.parametrize("graph", LOOP_GRAPHS, ids=name_of)
async def test_of_code_found_read_and_quoted_only_the_quote_is_a_source(graph: ModuleType) -> None:
    """Sprawdza w każdym grafie z narzędziami wiedzy przebieg „znajdź, przeczytaj, zacytuj" na
    kodzie aplikacji: model dostaje w następnej turze linie odczytanego pliku z numerami, a na
    listę źródeł trafia tylko fragment zacytowany jako przyczyna — szukanie i odczyt nie
    dokładają żadnego.

    Wyłapuje graf, w którym odczyt pliku tworzy źródło albo jego wynik nie wraca do modelu:
    wariant wymagający źródeł oddawałby rozwiązanie po samym zajrzeniu do kodu, albo model
    cytowałby linie, których nie widział."""
    read = {"path": GENERATOR_PATH, "from_line": 5, "to_line": 12}
    llm  = FakeLLMClient(turns=[
        tool_call_turn("find_code_text", {"exact": "Brak sekwencji numeracji"}, call_id="call_1"),
        tool_call_turn("read_code_file", read, call_id="call_2"),
        tool_call_turn(
            "quote_code",
            {"path": GENERATOR_PATH, "from_line": 8, "to_line": 10, "role": "cause"},
            call_id="call_3",
        ),
        tool_call_turn(graph.RESPOND_TOOL_NAME, {}, call_id="call_4"),
    ])

    final    = await run_graph(await loop_graph(graph, llm), graph.example_state())
    read_out = json.loads(llm.turn_calls[2].messages[-1].content)

    assert [line["line"] for line in read_out["lines"]] == list(range(5, 13))
    assert "if (!$sekwencja) {" in read_out["lines"][3]["text"]
    assert [ref.key for ref in final.sources] == [f"code:{GENERATOR_PATH}:8-10"]
    assert [entry.message for entry in final.log if entry.node == "run_tools"] == [
        "wywołania: find_code_text; źródła: 0",
        "wywołania: read_code_file; źródła: 0",
        "wywołania: quote_code; źródła: 1",
    ]


async def test_after_an_error_the_model_gets_another_turn() -> None:
    """Sprawdza, czy po odczycie wątku o nieznanym numerze (90019) model dostaje w następnej turze
    błąd z tym numerem, a przebieg idzie dalej: model czyta właściwy wątek (90011), który jako
    jedyny trafia do źródeł, i odpowiada.

    Wyłapuje graf, w którym pomyłka modelu w numerze kończy całe żądanie błędem albo od razu
    prowadzi do odpowiedzi: model ma dostać szansę, żeby wywołanie poprawić."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("read_tickets_thread", {"ticket_id": "90019"}, call_id="call_1"),
        tool_call_turn("read_tickets_thread", {"ticket_id": "90011"}, call_id="call_2"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final = await run_graph(await loop_graph(search, llm), search.example_state())
    error = llm.turn_calls[1].messages[-1].content

    assert is_error_json(error) and "90019" in error
    assert [ref.key for ref in final.sources]  == ["tickets:90011"]
    assert [entry.node for entry in final.log] == [
        "anonymize", "agent", "run_tools", "agent", "run_tools", "agent", "respond",
    ]


async def test_a_made_up_tool_goes_back_to_the_model_as_an_error() -> None:
    """Sprawdza, czy wywołanie narzędzia o zmyślonej nazwie (`find_tickets`) trafia do węzła
    narzędzi, a model dostaje w następnej turze błąd z tą nazwą i może odpowiedzieć. W dzienniku
    przebiegu zostaje ślad jednego błędu, a źródeł nie ma.

    Wyłapuje graf, w którym zmyślone narzędzie przerywa żądanie albo po cichu kończy pętlę
    odpowiedzią, tak jakby model nic nie wywołał."""
    llm = FakeLLMClient(turns=[
        tool_call_turn("find_tickets", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_2"),
    ])

    final = await run_graph(await loop_graph(search, llm), search.example_state())
    error = llm.turn_calls[1].messages[-1].content

    assert is_error_json(error) and "`find_tickets`" in error
    assert final.sources == []
    assert [entry.message for entry in final.log if entry.node == "run_tools"] == [
        "wywołania: find_tickets; źródła: 0; błędy: 1",
    ]


async def test_the_call_limit_holds_across_turns() -> None:
    """Sprawdza, czy przy limicie jednego odczytu wątku w sprawie drugi odczyt, zlecony w kolejnej
    turze, dostaje odmowę zamiast wyniku: na liście źródeł jest tylko pierwszy wątek, a narzędzie
    było wołane raz.

    Wyłapuje graf, w którym węzeł narzędzi nie widzi wcześniejszych tur i liczy limit od nowa
    w każdej: model czytałby wtedy dowolnie wiele wątków, po jednym na turę."""
    tools  = fake_agent_tools()
    reader = next(tool for tool in tools if tool.name == "read_tickets_thread")
    limits = {**LIMITS, "read_tickets_thread": 1}
    llm    = FakeLLMClient(turns=[
        tool_call_turn("read_tickets_thread", {"ticket_id": "90011"}, call_id="call_1"),
        tool_call_turn("read_tickets_thread", {"ticket_id": "90012"}, call_id="call_2"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_3"),
    ])

    final   = await run_graph(await loop_graph(search, llm, tools, limits), search.example_state())
    answers = tool_results(final.messages)

    assert not is_error_json(answers[0])
    assert is_error_json(answers[1])
    assert [ref.key for ref in final.sources] == ["tickets:90011"]
    assert len(reader.queries) == 1


async def test_a_dependency_failure_stops_the_run() -> None:
    """Sprawdza, czy awaria embeddera w narzędziu przerywa przebieg grafu wyjątkiem tej zależności,
    a model nie jest pytany po raz drugi.

    Wyłapuje graf, który po awarii zależności idzie dalej: model dostałby pustą albo błędną
    odpowiedź narzędzia i odpowiedział tak, jakby w bazie nic nie było, a wołający nie
    dowiedziałby się, że usługa nie działa."""
    tools = [find_tickets_vector_with_dead_embedder()]
    llm   = FakeLLMClient(turns=[
        tool_call_turn("find_tickets_vector", FAKE_SEARCH_ARGUMENTS, call_id="call_1"),
        tool_call_turn(search.RESPOND_TOOL_NAME, {}, call_id="call_2"),
    ])

    with pytest.raises(EmbeddingError):
        await run_graph(await loop_graph(search, llm, tools), search.example_state())

    assert len(llm.turn_calls) == 1
