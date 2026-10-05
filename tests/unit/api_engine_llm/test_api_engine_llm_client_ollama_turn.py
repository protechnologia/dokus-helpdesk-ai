import json

import pytest

from app.engine_llm import ChatMessage, LLMError, ToolCall, ToolDefinition
from app.engine_llm.client.ollama import OllamaLLMClient

# Tura z narzędziami w kliencie Ollamy (Chat Completions): jak rozmowa i narzędzia stają się
# żądaniem, jak odpowiedź serwera staje się turą modelu i czy strażniki okna kontekstu pilnują
# także tury. Bez serwera — testy wołają `_build_turn_request()` i `_to_turn()` wprost. Na żywym
# serwerze tura Ollamy nie była sprawdzana.

MODEL      = "model-lokalny:tag"
ENV_PREFIX = "LLM_ANONYMIZATION_"

SYSTEM = "Jesteś asystentem wdrożeniowca helpdesku."

SEARCH_ARGUMENTS = {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}

USER   = ChatMessage(role="user", content="Nie przychodzą przesyłki z e-Doręczeń")
SEARCH = ChatMessage(
    role       = "assistant",
    tool_calls = [ToolCall(call_id="call_1", name="find_tickets_vector",
                           arguments=SEARCH_ARGUMENTS)],
)
RESULT = ChatMessage(role="tool", call_id="call_1", content='{"tickets": []}')

TOOLS = [
    ToolDefinition(
        name        = "find_tickets_vector",
        description = "Szuka zgłoszeń.",
        parameters  = {"type": "object", "properties": {"problem": {"type": "string"}}},
    ),
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]


class StubFunction:
    """Nazwa narzędzia i jego argumenty jako tekst JSON, jak w wywołaniu od serwera."""

    def __init__(
        self,
        name:      str,  # np. "find_tickets_vector"
        arguments: str,  # np. '{"problem": "Brak przesyłek"}'
    ):
        self.name      = name
        self.arguments = arguments


class StubToolCall:
    """Jedno wywołanie narzędzia w atrapie odpowiedzi; `id` bywa puste na lokalnym serwerze."""

    def __init__(
        self,
        call_id:   str | None,  # np. "call_1" albo None
        name:      str,         # np. "find_tickets_vector"
        arguments: str,         # np. '{"problem": "Brak przesyłek"}'
    ):
        self.id       = call_id
        self.function = StubFunction(name, arguments)


class StubResponse:
    """
    Description:
    Jedna atrapa odpowiedzi Chat Completions na turę z narzędziami, z tym, co klient czyta:
    pierwszy wariant odpowiedzi z tekstem i wywołaniami oraz liczniki zużycia.
    """

    def __init__(
        self,
        content:           str | None = None,               # np. "Najpierw sprawdzę…"
        tool_calls:        list[StubToolCall] | None = None,
        prompt_tokens:     int = 900,                       # np. 6200
        completion_tokens: int = 40,                        # np. 310
        finish_reason:     str = "tool_calls",              # np. "length"
        choices:           bool = True,                     # False: odpowiedź bez wariantów
    ):
        message = type("Message", (), {"content": content, "tool_calls": tool_calls})()
        choice  = type("Choice", (), {"message": message, "finish_reason": finish_reason})()
        usage   = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

        self.choices = [choice] if choices else []
        self.usage   = type("Usage", (), usage)()
        self.model   = MODEL


def make_client(
    num_ctx: int = 8192,  # np. 1000 — okno kontekstu wpisane w konfiguracji
) -> OllamaLLMClient:
    """
    Description:
    Buduje klienta wskazującego domyślny adres lokalny. Nic tu nie sięga do sieci.

    Example args:
        num_ctx=8192

    Example result:
        OllamaLLMClient(model="model-lokalny:tag", num_ctx=8192)
    """
    return OllamaLLMClient(
        model             = MODEL,
        env_prefix        = ENV_PREFIX,
        num_ctx           = num_ctx,
        max_output_tokens = 500,
    )


def search_call(
    call_id: str | None = "call_1",  # np. None — serwer nie nadał identyfikatora
) -> StubToolCall:
    """
    Description:
    Wywołanie wyszukiwania w kształcie, w jakim oddaje je serwer.

    Example args:
        call_id="call_1"

    Example result:
        StubToolCall(id="call_1", function=StubFunction("find_tickets_vector", "{…}"))
    """
    return StubToolCall(
        call_id,
        "find_tickets_vector",
        json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),
    )


# --- żądanie --------------------------------------------------------------------------------

def test_the_conversation_becomes_chat_messages_in_order() -> None:
    """Sprawdza, czy rozmowa trafia do żądania jako wiadomości Chat Completions w tej samej
    kolejności: prompt systemowy jako pierwsza wiadomość, pytanie użytkownika, tura modelu
    z wywołaniem narzędzia (argumenty jako tekst JSON) i wynik narzędzia pod rolą `tool` ze
    wskazaniem wywołania.

    Wyłapuje rozmowę w kształcie, którego ten protokół nie przyjmuje, zgubiony prompt systemowy
    oraz wynik narzędzia bez powiązania z wywołaniem."""
    request = make_client()._build_turn_request(SYSTEM, [USER, SEARCH, RESULT], TOOLS)

    assert request["messages"] == [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER.content},
        {
            "role":       "assistant",
            "content":    "",
            "tool_calls": [{
                "id":       "call_1",
                "type":     "function",
                "function": {
                    "name":      "find_tickets_vector",
                    "arguments": json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),
                },
            }],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": RESULT.content},
    ]


def test_tools_go_under_the_function_key_and_no_call_is_forced() -> None:
    """Sprawdza, czy narzędzia trafiają do żądania w kolejności, w jakiej je podano, z nazwą,
    opisem i schematem pod kluczem `function`, a żądanie nie zawiera pola `tool_choice`.

    Wyłapuje definicje narzędzi w kształcie z innego API oraz wymuszenie wywołania, które część
    serwerów zgodnych z OpenAI odrzuca błędem."""
    request = make_client()._build_turn_request(SYSTEM, [USER], TOOLS)

    assert request["tools"] == [
        {
            "type":     "function",
            "function": {
                "name":        tool.name,
                "description": tool.description,
                "parameters":  tool.parameters,
            },
        }
        for tool in TOOLS
    ]
    assert "tool_choice" not in request


# --- odpowiedź ------------------------------------------------------------------------------

def test_tool_calls_are_read_with_their_arguments() -> None:
    """Sprawdza, czy z odpowiedzi serwera klient odczytuje wywołanie narzędzia: identyfikator,
    nazwę i argumenty zamienione z tekstu JSON na słownik, a zużycie zapisuje jako jedno
    wywołanie z tokenami wejścia i wyjścia oraz zerowym kosztem.

    Wyłapuje wywołanie zgubione albo z argumentami zostawionymi jako tekst oraz koszt naliczony
    za model, który chodzi na własnym sprzęcie."""
    response = StubResponse(tool_calls=[search_call()], prompt_tokens=900, completion_tokens=40)

    turn = make_client()._to_turn(response, elapsed_ms=41200.0)

    assert turn.message.tool_calls == [
        ToolCall(call_id="call_1", name="find_tickets_vector", arguments=SEARCH_ARGUMENTS),
    ]
    assert turn.message.provider_items  == []
    assert turn.usage.calls             == 1
    assert turn.usage.prompt_tokens     == 900
    assert turn.usage.completion_tokens == 40
    assert turn.usage.cost_usd          == 0.0
    assert turn.latency_ms              == 41200.0


def test_a_call_without_an_identifier_gets_its_number_in_the_turn() -> None:
    """Sprawdza, czy wywołania, którym serwer nie nadał identyfikatora, dostają numer kolejny
    w turze („call_1", „call_2"), a nadany identyfikator zostaje bez zmian.

    Wyłapuje turę odrzuconą albo wywołania nie do odróżnienia, gdy lokalny serwer pomija
    identyfikatory: wynik narzędzia musi wskazać, na które wywołanie odpowiada."""
    response = StubResponse(tool_calls=[search_call(None), search_call(None), search_call("abc")])

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert [call.call_id for call in turn.message.tool_calls] == ["call_1", "call_2", "abc"]


def test_a_turn_with_text_only_is_returned_as_text() -> None:
    """Sprawdza, czy odpowiedź z samym tekstem, bez wywołań narzędzi, wraca jako tura modelu z tym
    tekstem i pustą listą wywołań, a nie jako błąd.

    Wyłapuje klienta, który sam ocenia turę bez narzędzia: u tego dostawcy wywołanie nie jest
    wymuszane, więc tura z tekstem jest zwykłym wynikiem i rozstrzyga ją graf."""
    response = StubResponse(content="Nie wiem, czego szukać.", finish_reason="stop")

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert turn.message.content    == "Nie wiem, czego szukać."
    assert turn.message.tool_calls == []


@pytest.mark.parametrize(
    "response, fragment",
    [
        (StubResponse(finish_reason="length"), "length"),
        (StubResponse(choices=False),          "wariantu"),
    ],
    ids=["no-text-no-calls", "no-choices"],
)
def test_an_empty_turn_is_an_error(response: StubResponse, fragment: str) -> None:
    """Sprawdza, czy odpowiedź bez tekstu i bez wywołań narzędzi oraz odpowiedź bez żadnego
    wariantu kończą się wyjątkiem `LLMError` z powodem: w pierwszym przypadku jest to powód
    zakończenia od serwera, w drugim brak wariantu odpowiedzi.

    Wyłapuje pustą turę doklejoną do rozmowy: pętla agenta szłaby dalej na odpowiedzi, której
    model nie udzielił."""
    with pytest.raises(LLMError, match=fragment):
        make_client()._to_turn(response, elapsed_ms=1.0)


# --- okno kontekstu -------------------------------------------------------------------------

def test_a_turn_that_filled_the_window_is_refused() -> None:
    """Sprawdza, czy tura, przy której serwer naliczył tyle tokenów wejścia, ile ma okno kontekstu
    (tu 1000 z 1000), kończy się wyjątkiem `LLMError` o wypełnionym oknie.

    Wyłapuje turę przyjętą po tym, jak serwer uciął koniec rozmowy: model odpowiadałby bez
    ostatnich wyników narzędzi, a nic by tego nie zdradziło."""
    response = StubResponse(tool_calls=[search_call()], prompt_tokens=1000)

    with pytest.raises(LLMError, match="okno kontekstu"):
        make_client(num_ctx=1000)._to_turn(response, elapsed_ms=1.0)


def test_a_turn_the_server_read_only_partly_is_refused() -> None:
    """Sprawdza, czy tura, w której wysłaliśmy 60 000 znaków, a serwer naliczył tylko 900 tokenów
    wejścia, kończy się wyjątkiem `LLMError` o tym, że serwer przeczytał mniej, niż wysłaliśmy.

    Wyłapuje brak tego strażnika w turze z narzędziami: serwer z mniejszym oknem niż wpisane
    w konfiguracji ucina rozmowę po cichu, a w pętli rozmowa rośnie z każdą turą."""
    response = StubResponse(tool_calls=[search_call()], prompt_tokens=900)

    with pytest.raises(LLMError, match="przeczytał mniej"):
        make_client(num_ctx=32768)._to_turn(response, elapsed_ms=1.0, sent_chars=60_000)


async def test_a_conversation_too_long_for_the_window_is_refused_before_sending() -> None:
    """Sprawdza, czy rozmowa z wynikiem narzędzia na 90 000 znaków, która nie mieści się w oknie
    8192 tokenów, kończy turę wyjątkiem `LLMError` o za długim wejściu, zanim cokolwiek zostanie
    wysłane do serwera (test nie ma serwera, a mimo to dostaje ten błąd, a nie błąd połączenia).

    Wyłapuje turę wysłaną bez sprawdzenia długości: serwer uciąłby nadmiar po cichu, a model
    odpowiadałby na podstawie połowy przeczytanego wątku."""
    huge = ChatMessage(role="tool", call_id="call_1", content="x" * 90_000)

    with pytest.raises(LLMError, match="za długie"):
        await make_client().complete_turn(SYSTEM, [USER, SEARCH, huge], TOOLS)
