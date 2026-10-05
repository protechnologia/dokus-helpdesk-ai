import json
from typing import Annotated

import pytest
from pydantic import Field

from app.agent_graphs import GraphState, merge_sources
from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import RunToolsNode
from app.agent_tools import AgentTool, SourceRef
from app.agent_tools.docs.read_docs.fake import FakeReadDocsTool
from app.agent_tools.tickets.find_tickets_vector.fake import FakeFindTicketsVectorTool
from app.agent_tools.tickets.find_tickets_vector.models import FindTicketsVectorQuery
from app.agent_tools.tickets.read_tickets_card.fake import FakeReadTicketsCardTool
from app.agent_tools.tickets.read_tickets_card.models import ReadTicketsCardQuery
from app.agent_tools.tickets.read_tickets_thread.fake import FakeReadTicketsThreadTool
from app.engine_embedding import EmbeddingError
from app.engine_llm import ChatMessage, ToolCall
from tests.helpers_agent_tools import find_tickets_vector_with_dead_embedder

# Węzeł właściwy `run_tools` na atrapach narzędzi: co odpowiada modelowi na każde wywołanie, co
# dokłada do źródeł i czego nie wykonuje. Przebieg przez LangGraph sprawdzają testy integracyjne.

LIMITS = {
    "find_tickets_vector": 5,
    "read_tickets_card":   5,
    "read_tickets_thread": 3,
    "read_docs":           3,
}

SEARCH_ARGUMENTS = {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}


class State(GraphState):
    """Stan grafu z narzędziami wiedzy: pola wspólne plus `sources`."""

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)


def make_tools() -> dict[str, AgentTool]:
    """
    Description:
    Atrapy czterech narzędzi, po nazwie: wyszukiwanie zgłoszeń i trzy odczyty. Świeże na każdy
    test, bo zapisują zapytania, o które je pytano.

    Example args:
        (brak)

    Example result:
        {"find_tickets_vector": FakeFindTicketsVectorTool(), "read_tickets_card": …, …}
    """
    tools = [
        FakeFindTicketsVectorTool(),
        FakeReadTicketsCardTool(),
        FakeReadTicketsThreadTool(),
        FakeReadDocsTool(),
    ]

    return {tool.name: tool for tool in tools}


def state_with(
    *messages: ChatMessage,  # np. tool_call_turn("read_tickets_card", {…}) — ostatnia zleca
) -> State:
    """
    Description:
    Stan grafu z podaną rozmową; ostatnia wiadomość to tura modelu z wywołaniami narzędzi.

    Example args:
        messages=(tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]}),)

    Example result:
        State(input_text="x", messages=[ChatMessage(role="assistant", tool_calls=[…])])
    """
    return State(input_text="x", messages=list(messages))


def error_of(
    message: ChatMessage,  # np. ChatMessage(role="tool", content='{"error": "…"}')
) -> str:
    """
    Description:
    Komunikat błędu z wiadomości `tool`; pada, gdy wiadomość niesie wynik zamiast błędu.

    Example args:
        message=ChatMessage(role="tool", call_id="call_1", content='{"error": "nieznane…"}')

    Example result:
        "nieznane zgłoszenie: 90019"
    """
    body = json.loads(message.content)

    assert set(body) == {"error"}

    return body["error"]


async def test_a_read_gives_the_model_the_text_and_the_state_the_sources() -> None:
    """Sprawdza, czy po odczycie kart dwóch zgłoszeń model dostaje dokładnie ten tekst, który
    narzędzie przygotowuje dla modelu, a do stanu grafu trafiają dwa źródła, po jednym na kartę,
    z numerem zgłoszenia i tytułem.

    Wyłapuje węzeł, który podaje modelowi coś innego niż narzędzie albo gubi źródła odczytu:
    odpowiedź stałaby wtedy na materiale, którego nie ma na liście źródeł."""
    tools  = make_tools()
    reader = tools["read_tickets_card"]
    turn   = tool_call_turn("read_tickets_card", {"ticket_ids": ["90001", "90002"]})

    update   = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))
    expected = await FakeReadTicketsCardTool().search(
        ReadTicketsCardQuery(ticket_ids=["90001", "90002"]),
    )

    assert update["messages"][0].content == reader.render_for_model(expected)
    assert update["sources"]             == reader.cite(expected)
    assert [ref.key for ref in update["sources"]] == ["tickets:90001", "tickets:90002"]


async def test_a_search_gives_the_text_and_no_sources() -> None:
    """Sprawdza, czy po wyszukiwaniu zgłoszeń model dostaje wynik z numerami, a zmiana stanu w ogóle
    nie zawiera pola źródeł.

    Wyłapuje węzeł, który dopisuje do źródeł to, co model tylko znalazł: źródłem ma być wyłącznie
    materiał przeczytany."""
    tools = make_tools()
    turn  = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS)

    update = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))
    found  = json.loads(update["messages"][0].content)

    assert [ticket["ticket_id"] for ticket in found["tickets"]] == ["90001", "90002", "90003"]
    assert "sources" not in update


async def test_the_tool_gets_the_arguments_as_its_own_query() -> None:
    """Sprawdza, czy argumenty wywołania docierają do narzędzia jako obiekt jego własnej klasy
    zapytania, z tymi samymi wartościami, które podał model.

    Wyłapuje węzeł, który woła narzędzie surowym słownikiem albo zmienia argumenty po drodze:
    narzędzie szukałoby wtedy czegoś innego, niż model zlecił."""
    tools = make_tools()
    turn  = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS)

    await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))

    assert tools["find_tickets_vector"].queries == [FindTicketsVectorQuery(**SEARCH_ARGUMENTS)]


async def test_every_call_of_a_turn_gets_its_own_answer_in_order() -> None:
    """Sprawdza, czy na turę z trzema wywołaniami węzeł odpowiada trzema wiadomościami `tool`,
    w kolejności wywołań i każdą z identyfikatorem swojego wywołania, a źródła z obu odczytów
    trafiają do jednej listy.

    Wyłapuje odpowiedź zgubioną albo przypisaną do innego wywołania: dostawca modelu odrzuca
    rozmowę, w której wywołanie nie ma swojego wyniku."""
    tools = make_tools()
    turn  = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="a", name="find_tickets_vector", arguments=SEARCH_ARGUMENTS),
            ToolCall(call_id="b", name="read_tickets_card", arguments={"ticket_ids": ["90001"]}),
            ToolCall(call_id="c", name="read_docs",
                     arguments={"section_ids": ["adm-kancelaria-edoreczenia"]}),
        ],
    )

    update = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))

    assert [message.role for message in update["messages"]]    == ["tool", "tool", "tool"]
    assert [message.call_id for message in update["messages"]] == ["a", "b", "c"]
    assert [ref.key for ref in update["sources"]] == [
        "tickets:90001",
        "docs:adm-kancelaria-edoreczenia",
    ]


async def test_a_tool_outside_the_node_is_refused_and_the_rest_runs() -> None:
    """Sprawdza, czy wywołanie narzędzia, którego węzeł nie dostał (tu `read_docs` w węźle z samymi
    narzędziami zgłoszeń), dostaje w miejscu wyniku błąd z nazwą tego narzędzia, a odczyt karty
    z tej samej tury wykonuje się normalnie i dokłada źródło.

    Wyłapuje węzeł, który wykonuje narzędzie spoza listy dozwolonych w grafie albo przez jedno
    takie wywołanie przerywa całą turę."""
    tools   = make_tools()
    allowed = [tool for name, tool in tools.items() if name != "read_docs"]
    turn    = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="a", name="read_docs",
                     arguments={"section_ids": ["adm-kancelaria-edoreczenia"]}),
            ToolCall(call_id="b", name="read_tickets_card", arguments={"ticket_ids": ["90001"]}),
        ],
    )

    update = await RunToolsNode(allowed, LIMITS).run(state_with(turn))

    assert "`read_docs`" in error_of(update["messages"][0])
    assert tools["read_docs"].queries == []
    assert [ref.key for ref in update["sources"]] == ["tickets:90001"]


@pytest.mark.parametrize(
    "arguments, field",
    [
        ({"problem": "Brak przesyłek"},                 "symptoms"),
        ({**SEARCH_ARGUMENTS, "limit": 50},             "limit"),
        ({"problem": "", "symptoms": "pusta skrzynka"}, "problem"),
    ],
    ids=["missing", "unknown", "empty"],
)
async def test_invalid_arguments_come_back_to_the_model_naming_the_field(
    arguments: dict,
    field:     str,
) -> None:
    """Sprawdza, czy wywołanie z błędnymi argumentami (brak pola, pole spoza schematu, puste pole)
    dostaje w miejscu wyniku błąd, który nazywa narzędzie i wadliwe pole, a samo narzędzie nie
    jest wołane.

    Wyłapuje węzeł, który przepuszcza złe argumenty do narzędzia albo kończy żądanie błędem:
    model ma dostać wskazówkę, co poprawić, i spróbować jeszcze raz."""
    tools = make_tools()
    turn  = tool_call_turn("find_tickets_vector", arguments)

    update = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))
    error  = error_of(update["messages"][0])

    assert "`find_tickets_vector`" in error
    assert f"{field}:"             in error
    assert tools["find_tickets_vector"].queries == []


async def test_an_error_of_the_tool_comes_back_and_the_rest_runs() -> None:
    """Sprawdza, czy odczyt wątku o numerze, którego nie ma w bazie (90019), dostaje w miejscu
    wyniku błąd z tym numerem i nie dokłada źródła, a odczyt istniejącego wątku z tej samej tury
    wykonuje się i dokłada swoje.

    Wyłapuje węzeł, który przy pomyłce modelu w numerze przerywa przebieg albo gubi wyniki
    pozostałych wywołań: model ma poprawić jedno wywołanie, a nie tracić całą turę."""
    tools = make_tools()
    turn  = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="a", name="read_tickets_thread", arguments={"ticket_id": "90019"}),
            ToolCall(call_id="b", name="read_tickets_thread", arguments={"ticket_id": "90011"}),
        ],
    )

    update = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))

    assert "90019" in error_of(update["messages"][0])
    assert json.loads(update["messages"][1].content)["ticket_id"] == "90011"
    assert [ref.key for ref in update["sources"]] == ["tickets:90011"]


async def test_a_call_over_the_limit_is_refused_without_running_the_tool() -> None:
    """Sprawdza, czy przy limicie jednego wyszukiwania drugie dostaje w miejscu wyniku odmowę
    z nazwą narzędzia, a narzędzie jest wołane tylko raz.

    Wyłapuje węzeł, który limitu nie egzekwuje albo najpierw wykonuje narzędzie, a dopiero potem
    odmawia: model mógłby szukać bez ograniczeń, a każde wywołanie kosztuje."""
    tools  = make_tools()
    limits = {**LIMITS, "find_tickets_vector": 1}
    node   = RunToolsNode(list(tools.values()), limits)
    first  = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS, call_id="call_1")
    second = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS, call_id="call_2")

    done    = await node.run(state_with(first))
    refused = await node.run(state_with(first, *done["messages"], second))

    assert "`find_tickets_vector`" in error_of(refused["messages"][0])
    assert refused["messages"][0].call_id == "call_2"
    assert len(tools["find_tickets_vector"].queries) == 1


async def test_a_failed_call_does_not_use_up_the_limit() -> None:
    """Sprawdza, czy przy limicie jednego odczytu wątku model, który najpierw podał nieznany numer
    i dostał błąd, może w następnej turze odczytać właściwy wątek.

    Wyłapuje liczenie nieudanych wywołań do limitu: model dostałby radę „popraw wywołanie",
    a zaraz potem odmowę, bo poprawka byłaby już ponad limit."""
    tools  = make_tools()
    limits = {**LIMITS, "read_tickets_thread": 1}
    node   = RunToolsNode(list(tools.values()), limits)
    wrong  = tool_call_turn("read_tickets_thread", {"ticket_id": "90019"}, call_id="call_1")
    right  = tool_call_turn("read_tickets_thread", {"ticket_id": "90011"}, call_id="call_2")

    failed = await node.run(state_with(wrong))
    fixed  = await node.run(state_with(wrong, *failed["messages"], right))

    assert json.loads(fixed["messages"][0].content)["ticket_id"] == "90011"


async def test_a_dependency_failure_stops_the_node() -> None:
    """Sprawdza, czy awaria embeddera w narzędziu wychodzi z węzła jako wyjątek, a nie jako błąd
    podany modelowi w miejscu wyniku.

    Wyłapuje węzeł, który połyka awarię zależności: model dostałby radę, żeby poprawić wywołanie,
    choć żadna poprawka nie pomoże, a wołający nie dowiedziałby się, że usługa nie działa."""
    turn = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS)
    node = RunToolsNode([find_tickets_vector_with_dead_embedder()], LIMITS)

    with pytest.raises(EmbeddingError):
        await node.run(state_with(turn))


async def test_the_log_names_tools_and_counts_and_quotes_nothing() -> None:
    """Sprawdza, czy wpis węzła w dzienniku przebiegu wymienia nazwy wywołanych narzędzi oraz
    liczbę źródeł i błędów, a nie zawiera argumentów wywołania ani treści wyniku.

    Wyłapuje wpis, który cytuje zapytanie modelu albo odczytaną kartę: to dane klienta, a dziennik
    wraca do wołającego razem z odpowiedzią."""
    tools = make_tools()
    turn  = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="a", name="read_tickets_card", arguments={"ticket_ids": ["90001"]}),
            ToolCall(call_id="b", name="read_tickets_thread", arguments={"ticket_id": "90019"}),
        ],
    )

    update = await RunToolsNode(list(tools.values()), LIMITS).run(state_with(turn))

    assert [entry.node for entry in update["log"]] == ["run_tools"]
    assert update["log"][0].message == (
        "wywołania: read_tickets_card, read_tickets_thread; źródła: 1; błędy: 1"
    )


@pytest.mark.parametrize(
    "tools, limits",
    [
        ([],                                                     LIMITS),
        ([FakeReadTicketsCardTool(), FakeReadTicketsCardTool()], LIMITS),
        ([FakeReadTicketsCardTool()],                            {"read_docs": 3}),
    ],
    ids=["no-tools", "same-name-twice", "no-limit"],
)
def test_a_badly_assembled_node_is_refused(tools: list[AgentTool], limits: dict[str, int]) -> None:
    """Sprawdza, czy węzła nie da się zbudować bez narzędzi, z dwoma narzędziami o tej samej nazwie
    ani z narzędziem, które nie ma limitu wywołań.

    Wyłapuje błąd składania grafu dopiero w trakcie żądania: narzędzie bez limitu mogłoby być wołane
    bez końca, a z dwóch o jednej nazwie wykonywałoby się to, które akurat stoi dalej na liście."""
    with pytest.raises(ValueError):
        RunToolsNode(tools, limits)
