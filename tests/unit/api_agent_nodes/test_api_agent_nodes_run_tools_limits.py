import json

from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import calls_over_limit, limit_exceeded_text
from app.engine_llm import ChatMessage, ToolCall

# Liczenie wywołań narzędzi wobec limitów: funkcja wspólna dla atrapy `run_tools` i węzła
# właściwego. Sprawdzamy ją na samych wiadomościach, bez grafu.


def _answer(
    call_id: str,  # np. "call_1"
) -> ChatMessage:
    """
    Description:
    Wiadomość `tool` z wynikiem wywołania — stoi w rozmowie między turami modelu.

    Example args:
        call_id="call_1"

    Example result:
        ChatMessage(role="tool", call_id="call_1", content="{}")
    """
    return ChatMessage(role="tool", call_id=call_id, content="{}")


def _find(
    call_id: str,  # np. "call_1"
) -> ChatMessage:
    """
    Description:
    Tura modelu z jednym wywołaniem `find_tickets_vector`.

    Example args:
        call_id="call_1"

    Example result:
        ChatMessage(role="assistant", tool_calls=[ToolCall(name="find_tickets_vector", …)])
    """
    return tool_call_turn("find_tickets_vector", {"problem": "x", "symptoms": "y"}, call_id=call_id)


def test_calls_within_the_limit_are_not_refused() -> None:
    """Drugie wywołanie przy limicie 2 → mieści się: limit mówi, ile wywołań wolno, a nie
    po ilu przestać."""
    messages = [_find("call_1"), _answer("call_1"), _find("call_2")]

    assert calls_over_limit(messages, {"find_tickets_vector": 2}) == set()


def test_a_call_over_the_limit_is_refused() -> None:
    """Trzecie wywołanie przy limicie 2 → ponad limit, wskazane po `call_id`."""
    messages = [
        _find("call_1"), _answer("call_1"),
        _find("call_2"), _answer("call_2"),
        _find("call_3"),
    ]

    assert calls_over_limit(messages, {"find_tickets_vector": 2}) == {"call_3"}


def test_each_tool_is_counted_on_its_own() -> None:
    """Dwa narzędzia w rozmowie → każde liczone osobno: wyczerpany limit wyszukiwania nie
    blokuje odczytu."""
    read     = tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]}, call_id="call_3")
    messages = [_find("call_1"), _answer("call_1"), _find("call_2"), _answer("call_2"), read]
    limits   = {"find_tickets_vector": 2, "read_tickets_card": 1}

    assert calls_over_limit(messages, limits) == set()


def test_calls_in_one_turn_are_counted_in_order() -> None:
    """Trzy wywołania tego samego narzędzia w jednej turze przy limicie 2 → dwa pierwsze
    przechodzą, trzecie jest ponad limit."""
    turn = ChatMessage(
        role       = "assistant",
        tool_calls = [
            ToolCall(call_id="call_1", name="read_docs", arguments={"section_ids": ["a"]}),
            ToolCall(call_id="call_2", name="read_docs", arguments={"section_ids": ["b"]}),
            ToolCall(call_id="call_3", name="read_docs", arguments={"section_ids": ["c"]}),
        ],
    )

    assert calls_over_limit([turn], {"read_docs": 2}) == {"call_3"}


def test_a_tool_without_a_limit_is_never_refused() -> None:
    """Narzędzie bez wpisu w limitach → bez limitu: odmawia się tylko tego, co skonfigurowano."""
    messages = [_find("call_1"), _answer("call_1"), _find("call_2"), _answer("call_2"), _find("c3")]

    assert calls_over_limit(messages, {"read_docs": 1}) == set()


def test_an_empty_conversation_has_nothing_to_refuse() -> None:
    """Brak wiadomości → pusty zbiór, nie błąd."""
    assert calls_over_limit([], {"find_tickets_vector": 1}) == set()


def test_the_refusal_is_json_naming_the_tool_and_the_limit() -> None:
    """Tekst dla modelu → JSON z polem `error`, w którym stoi nazwa narzędzia, limit i co dalej:
    model ma odpowiedzieć na podstawie tego, co już ma, a nie próbować ponownie."""
    body = json.loads(limit_exceeded_text("read_tickets_thread", 2))

    assert set(body) == {"error"}
    assert "`read_tickets_thread`" in body["error"]
    assert "(2)"                   in body["error"]
    assert "odpowiedz na podstawie tego, co już masz" in body["error"]
