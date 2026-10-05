import json

from app.agent_nodes.agent import tool_call_turn
from app.agent_nodes.run_tools import calls_over_limit, limit_exceeded_text
from app.agent_tools.base import error_as_json
from app.engine_llm import ChatMessage, ToolCall

# Liczenie wywołań narzędzi wobec limitów: funkcja wspólna dla atrapy `run_tools` i węzła
# właściwego. Sprawdzamy ją na samych wiadomościach, bez grafu.


def _answer(
    call_id: str,         # np. "call_1"
    content: str = "{}",  # np. error_as_json("nieznane zgłoszenie: 90019")
) -> ChatMessage:
    """
    Description:
    Wiadomość `tool` z wynikiem wywołania — stoi w rozmowie między turami modelu.

    Example args:
        call_id="call_1"
        content="{}"

    Example result:
        ChatMessage(role="tool", call_id="call_1", content="{}")
    """
    return ChatMessage(role="tool", call_id=call_id, content=content)


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
    """Sprawdza, czy przy limicie dwóch wywołań drugie wyszukiwanie zgłoszeń jeszcze się mieści
    i nie jest wskazane do odmowy.

    Wyłapuje pomyłkę o jeden w liczeniu: limit mówi, ile wywołań wolno wykonać, więc odmowa już przy
    drugim zabierałaby modelowi jedno należne wywołanie."""
    messages = [_find("call_1"), _answer("call_1"), _find("call_2")]

    assert calls_over_limit(messages, {"find_tickets_vector": 2}) == set()


def test_a_call_over_the_limit_is_refused() -> None:
    """Sprawdza, czy przy limicie dwóch wywołań trzecie wyszukiwanie zgłoszeń jest wskazane do
    odmowy, po swoim identyfikatorze („call_3").

    Wyłapuje limit, który nie działa albo wskazuje nie to wywołanie: model mógłby szukać bez
    ograniczeń albo dostałby odmowę zamiast wyniku, który mu się należał."""
    messages = [
        _find("call_1"), _answer("call_1"),
        _find("call_2"), _answer("call_2"),
        _find("call_3"),
    ]

    assert calls_over_limit(messages, {"find_tickets_vector": 2}) == {"call_3"}


def test_a_call_answered_with_an_error_does_not_count() -> None:
    """Sprawdza, czy wcześniejsze wywołanie, na które model dostał błąd zamiast wyniku, nie liczy
    się do limitu: przy limicie 1 kolejne wyszukiwanie po nieudanym nie jest wskazane do odmowy,
    a po udanym jest.

    Wyłapuje liczenie nieudanych wywołań na równi z udanymi: model, który pomylił argument
    i dostał radę, żeby go poprawić, trafiałby z poprawką na wyczerpany limit."""
    error  = error_as_json("błędne argumenty")
    failed = [_find("call_1"), _answer("call_1", error), _find("call_2")]
    done   = [_find("call_1"), _answer("call_1"), _find("call_2")]

    assert calls_over_limit(failed, {"find_tickets_vector": 1}) == set()
    assert calls_over_limit(done, {"find_tickets_vector": 1})   == {"call_2"}


def test_each_tool_is_counted_on_its_own() -> None:
    """Sprawdza, czy wywołania każdego narzędzia liczą się osobno: po dwóch wyszukiwaniach, które
    wyczerpują limit wyszukiwania, pierwszy odczyt kart przy własnym limicie 1 nie jest wskazany do
    odmowy.

    Wyłapuje wspólny licznik dla wszystkich narzędzi: wyczerpany limit wyszukiwania blokowałby wtedy
    odczyt znalezionych zgłoszeń."""
    read     = tool_call_turn("read_tickets_card", {"ticket_ids": ["90001"]}, call_id="call_3")
    messages = [_find("call_1"), _answer("call_1"), _find("call_2"), _answer("call_2"), read]
    limits   = {"find_tickets_vector": 2, "read_tickets_card": 1}

    assert calls_over_limit(messages, limits) == set()


def test_calls_in_one_turn_are_counted_in_order() -> None:
    """Sprawdza, czy trzy wywołania tego samego narzędzia zgłoszone w jednej turze modelu są liczone
    po kolei: przy limicie 2 dwa pierwsze przechodzą, a trzecie jest wskazane do odmowy.

    Wyłapuje liczenie, które patrzy tylko na wcześniejsze tury: model obszedłby wtedy limit,
    zgłaszając wiele wywołań naraz."""
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
    """Sprawdza, czy narzędzie, którego nie ma w limitach, nie jest ograniczane: trzecie z rzędu
    wyszukiwanie zgłoszeń nie jest wskazane do odmowy, gdy limit ustawiono tylko dla `read_docs`.

    Wyłapuje odmowę wywołań narzędzia, którego nikt nie ograniczył, na przykład przez potraktowanie
    braku limitu jak zera."""
    messages = [_find("call_1"), _answer("call_1"), _find("call_2"), _answer("call_2"), _find("c3")]

    assert calls_over_limit(messages, {"read_docs": 1}) == set()


def test_an_empty_conversation_has_nothing_to_refuse() -> None:
    """Sprawdza, czy dla pustej rozmowy funkcja licząca wywołania oddaje pusty zbiór, a nie błąd.

    Wyłapuje awarię na pustej liście wiadomości: funkcja wyjmuje z rozmowy ostatnią turę, więc bez
    osobnej obsługi tego przypadku wywróciłaby przebieg."""
    assert calls_over_limit([], {"find_tickets_vector": 1}) == set()


def test_the_refusal_is_json_naming_the_tool_and_the_limit() -> None:
    """Sprawdza, czy odmowa, którą model dostaje zamiast wyniku narzędzia, jest JSON-em z jednym
    polem `error`, a w nim stoi nazwa narzędzia, wyczerpany limit (tu 2) i wskazówka, żeby
    odpowiedzieć na podstawie tego, co już jest.

    Wyłapuje odmowę w innym kształcie niż wyniki narzędzi albo bez wskazówki, co dalej: model mógłby
    wtedy próbować tego samego wywołania ponownie."""
    body = json.loads(limit_exceeded_text("read_tickets_thread", 2))

    assert set(body) == {"error"}
    assert "`read_tickets_thread`" in body["error"]
    assert "(2)"                   in body["error"]
    assert "odpowiedz na podstawie tego, co już masz" in body["error"]
