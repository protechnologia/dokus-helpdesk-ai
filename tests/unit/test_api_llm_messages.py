import pytest
from pydantic import ValidationError

from app.llm import ChatMessage, ToolCall


def test_a_tool_result_must_point_at_its_call() -> None:
    """Wiadomość `tool` bez `call_id` → ValidationError: dostawca odrzuciłby rozmowę z wynikiem
    narzędzia, którego nie da się przypisać do wywołania."""
    with pytest.raises(ValidationError):
        ChatMessage(role="tool", content="Znalezione zgłoszenia: 3")


def test_only_the_model_requests_tools() -> None:
    """Wywołania narzędzi w wiadomości `user` → ValidationError: narzędzia zleca wyłącznie model."""
    with pytest.raises(ValidationError):
        ChatMessage(role="user", tool_calls=[ToolCall(call_id="call_1", name="find_tickets")])


def test_a_model_turn_with_a_tool_call_is_valid() -> None:
    """Odpowiedź modelu z wywołaniem i wynik z tym samym `call_id` → oba poprawne."""
    call = ToolCall(call_id="call_1", name="find_tickets", arguments={"problem": "x"})

    request = ChatMessage(role="assistant", tool_calls=[call])
    answer  = ChatMessage(role="tool", content="Znalezione zgłoszenia: 3", call_id="call_1")

    assert request.tool_calls[0].arguments["problem"] == "x"
    assert answer.call_id == request.tool_calls[0].call_id
