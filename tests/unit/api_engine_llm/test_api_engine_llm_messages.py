import pytest
from pydantic import ValidationError

from app.engine_llm import ChatMessage, ToolCall, ToolDefinition


def test_a_tool_result_must_point_at_its_call() -> None:
    """Sprawdza, czy wiadomość z wynikiem narzędzia (`tool`) bez `call_id` jest odrzucana wyjątkiem
    `ValidationError`.

    Wyłapuje model wiadomości, który taki wynik przepuszcza: nie da się go przypisać do żadnego
    wywołania, więc dostawca odrzuciłby całą rozmowę dopiero w środku pętli agenta."""
    with pytest.raises(ValidationError):
        ChatMessage(role="tool", content="Znalezione zgłoszenia: 3")


def test_only_the_model_requests_tools() -> None:
    """Sprawdza, czy wiadomość `user` z wywołaniem narzędzia jest odrzucana wyjątkiem
    `ValidationError`.

    Wyłapuje model wiadomości, który pozwala zlecać narzędzia komuś innemu niż model: taka rozmowa
    jest błędna i dostawca by jej nie przyjął."""
    call = ToolCall(call_id="call_1", name="find_tickets_vector")

    with pytest.raises(ValidationError):
        ChatMessage(role="user", tool_calls=[call])


def test_a_model_turn_with_a_tool_call_is_valid() -> None:
    """Sprawdza, czy poprawna para wiadomości daje się zbudować: odpowiedź modelu z wywołaniem
    narzędzia i wynik narzędzia z tym samym `call_id`, a argumenty wywołania zostają takie, jak je
    podano.

    Wyłapuje zbyt ostrą walidację, która odrzuca zwykłą turę z narzędziem: pętla agenta nie mogłaby
    wtedy zapisać ani wywołania, ani jego wyniku."""
    call = ToolCall(call_id="call_1", name="find_tickets_vector", arguments={"problem": "x"})

    request = ChatMessage(role="assistant", tool_calls=[call])
    answer  = ChatMessage(role="tool", content="Znalezione zgłoszenia: 3", call_id="call_1")

    assert request.tool_calls[0].arguments["problem"] == "x"
    assert answer.call_id == request.tool_calls[0].call_id


def test_a_model_turn_carries_provider_items_as_they_came() -> None:
    """Sprawdza, czy element dostawcy dołączony do tury modelu (tu zmyślony zapis rozumowania)
    zostaje w wiadomości bez zmian, a wiadomość bez takich elementów ma pustą listę.

    Wyłapuje model wiadomości, który ten element gubi albo przerabia: klient musi go odesłać
    dostawcy w następnej turze dokładnie taki, jaki przyszedł."""
    reasoning = {"type": "reasoning", "id": "rs_1", "encrypted_content": "gAAAAB…"}

    turn = ChatMessage(role="assistant", content="", provider_items=[reasoning])

    assert turn.provider_items == [reasoning]
    assert ChatMessage(role="assistant").provider_items == []


@pytest.mark.parametrize("role", ["user", "tool"])
def test_only_a_model_turn_carries_provider_items(role: str) -> None:
    """Sprawdza, czy element dostawcy w wiadomości `user` albo `tool` jest odrzucany wyjątkiem
    `ValidationError`.

    Wyłapuje model wiadomości, który przyjmuje takie elementy poza turą modelu: rozumowanie i bloki
    myślenia należą do odpowiedzi modelu, a dostawca odrzuciłby je w innym miejscu rozmowy."""
    reasoning = {"type": "reasoning", "id": "rs_1"}

    with pytest.raises(ValidationError):
        ChatMessage(role=role, content="x", call_id="call_1", provider_items=[reasoning])


@pytest.mark.parametrize("name", ["respond gate close", "odpowiedź", "x" * 65, ""])
def test_a_tool_name_outside_the_provider_format_is_rejected(name: str) -> None:
    """Sprawdza, czy definicja narzędzia odrzuca nazwę, której dostawcy nie przyjmą: ze spacją, ze
    znakiem spoza ASCII, dłuższą niż 64 znaki albo pustą.

    Wyłapuje definicję, która taką nazwę przepuszcza: Claude i OpenAI odrzuciłyby wtedy całe
    żądanie, a błąd wyszedłby dopiero przy rozmowie z modelem."""
    with pytest.raises(ValidationError):
        ToolDefinition(name=name, description="Opis.", parameters={"type": "object"})
