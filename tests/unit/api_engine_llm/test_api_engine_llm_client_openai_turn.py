import json

import pytest

from app.engine_llm import ChatMessage, LLMError, ToolCall, ToolDefinition
from app.engine_llm.client.openai import OpenAILLMClient
from app.engine_llm.pricing.openai import calculate_cost_usd

# Tura z narzędziami w kliencie OpenAI (API Responses): jak rozmowa i narzędzia stają się
# żądaniem i jak odpowiedź dostawcy staje się turą modelu. Bez sieci — testy wołają
# `_build_turn_request()` i `_to_turn()` wprost. Żywego dostawcę sprawdza test `llm_live`.

API_KEY = "sk-proj-test-key"
MODEL   = "gpt-6.1-sol"

SYSTEM = "Jesteś asystentem wdrożeniowca helpdesku."

SEARCH_ARGUMENTS = {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}

USER   = ChatMessage(role="user", content="Nie przychodzą przesyłki z e-Doręczeń")
RESULT = ChatMessage(role="tool", call_id="call_1", content='{"tickets": []}')

TOOLS = [
    ToolDefinition(
        name        = "find_tickets_vector",
        description = "Szuka zgłoszeń.",
        parameters  = {"type": "object", "properties": {"problem": {"type": "string"}}},
    ),
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]

# Elementy, które dostawca oddał w poprzedniej turze: rozumowanie i wywołanie narzędzia.
REASONING_ITEM = {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "gAAA…"}
CALL_ITEM      = {
    "type":      "function_call",
    "id":        "fc_1",
    "call_id":   "call_1",
    "name":      "find_tickets_vector",
    "arguments": json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),
    "status":    "completed",
}


class StubItem:
    """
    Description:
    Jeden element odpowiedzi API Responses w atrapie: pola dostępne jak atrybuty i `model_dump()`
    oddający je jako słownik, tak jak modele SDK. Pole o wartości `None` to pole, którego dostawca
    nie wypełnił.
    """

    def __init__(
        self,
        **fields,  # np. type="function_call", call_id="call_1", name="read_docs", arguments="{}"
    ):
        self._fields = fields
        self.__dict__.update(fields)

    def model_dump(
        self,
        mode:         str  = "python",  # np. "json"
        exclude_none: bool = False,     # np. True
    ) -> dict:
        """
        Description:
        Oddaje pola elementu jako słownik; z `exclude_none` bez pól pustych.

        Example args:
            mode="json"
            exclude_none=True

        Example result:
            {"type": "function_call", "call_id": "call_1", "name": "read_docs", "arguments": "{}"}
        """
        return {
            name: value
            for name, value in self._fields.items()
            if not (exclude_none and value is None)
        }


class StubUsage:
    """
    Description:
    Liczniki zużycia w atrapie odpowiedzi. Obie klasy cache przychodzą zagnieżdżone i siedzą
    WEWNĄTRZ `input_tokens`, jak w prawdziwym API.
    """

    def __init__(
        self,
        input_tokens:       int,      # np. 5000 — całe wejście, razem z licznikami cache
        output_tokens:      int,      # np. 200
        cached_tokens:      int = 0,  # np. 3000
        cache_write_tokens: int = 0,  # np. 1500
    ):
        details = {"cached_tokens": cached_tokens, "cache_write_tokens": cache_write_tokens}

        self.input_tokens         = input_tokens
        self.output_tokens        = output_tokens
        self.input_tokens_details = type("Details", (), details)()


class StubResponse:
    """
    Description:
    Jedna atrapa odpowiedzi API Responses na turę z narzędziami, z tym, co klient czyta.
    """

    def __init__(
        self,
        output:            list[StubItem],     # np. [StubItem(type="function_call", …)]
        output_text:       str = "",           # np. "Najpierw sprawdzę…"
        usage:             StubUsage | None = None,
        status:            str = "completed",  # np. "incomplete"
        incomplete_reason: str | None = None,  # np. "max_output_tokens"
    ):
        self.output             = output
        self.output_text        = output_text
        self.usage              = usage or StubUsage(input_tokens=100, output_tokens=10)
        self.model              = MODEL
        self.status             = status
        self.incomplete_details = type("Incomplete", (), {"reason": incomplete_reason})()


def make_client(
    model: str = MODEL,  # np. "gpt-5.4-mini"
) -> OpenAILLMClient:
    """
    Description:
    Buduje klienta z atrapą klucza. Nic tu nie sięga do sieci.

    Example args:
        model="gpt-5.4-mini"

    Example result:
        OpenAILLMClient(model="gpt-5.4-mini")
    """
    return OpenAILLMClient(api_key=API_KEY, model=model, temperature=0.0)


def call_item(
    call_id:   str = "call_1",                                          # np. "call_2"
    name:      str = "find_tickets_vector",                             # np. "read_docs"
    arguments: str = json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),  # tekst JSON od modelu
) -> StubItem:
    """
    Description:
    Wywołanie narzędzia w kształcie, w jakim oddaje je dostawca: argumenty jako tekst JSON.

    Example args:
        call_id="call_1"
        name="find_tickets_vector"

    Example result:
        StubItem(type="function_call", call_id="call_1", name="find_tickets_vector", …)
    """
    return StubItem(
        type      = "function_call",
        id        = f"fc_{call_id}",
        call_id   = call_id,
        name      = name,
        arguments = arguments,
        status    = "completed",
        caller    = None,
    )


# --- żądanie --------------------------------------------------------------------------------

def test_the_conversation_becomes_input_items_in_order() -> None:
    """Sprawdza, czy rozmowa złożona z pytania użytkownika, tury modelu z wywołaniem narzędzia
    i wyniku tego narzędzia trafia do żądania jako trzy elementy w tej samej kolejności, z
    argumentami wywołania jako tekstem JSON, a prompt systemowy idzie osobno, w polu
    `instructions`.

    Wyłapuje rozmowę przetłumaczoną w złej kolejności albo w kształcie, którego to API nie
    przyjmuje, oraz wynik narzędzia, który nie wskazuje wywołania, na które odpowiada."""
    turn    = ChatMessage(
        role       = "assistant",
        tool_calls = [ToolCall(call_id="call_1", name="find_tickets_vector",
                               arguments=SEARCH_ARGUMENTS)],
    )
    request = make_client()._build_turn_request(SYSTEM, [USER, turn, RESULT], TOOLS)

    assert request["instructions"] == SYSTEM
    assert request["input"]        == [
        {"role": "user", "content": USER.content},
        {
            "type":      "function_call",
            "call_id":   "call_1",
            "name":      "find_tickets_vector",
            "arguments": json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),
        },
        {"type": "function_call_output", "call_id": "call_1", "output": RESULT.content},
    ]


def test_a_turn_of_this_provider_goes_back_untouched() -> None:
    """Sprawdza, czy tura modelu, która niesie elementy oddane przez dostawcę (rozumowanie
    i wywołanie narzędzia), wraca do niego dokładnie tymi elementami, w tej samej kolejności
    i bez dokładania drugiego wywołania złożonego z naszych pól.

    Wyłapuje zgubienie albo przestawienie elementów rozumowania oraz wywołanie wysłane dwa razy:
    dostawca odrzuca wtedy następną turę rozmowy."""
    turn    = ChatMessage(
        role           = "assistant",
        tool_calls     = [ToolCall(call_id="call_1", name="find_tickets_vector",
                                   arguments=SEARCH_ARGUMENTS)],
        provider_items = [REASONING_ITEM, CALL_ITEM],
    )
    request = make_client()._build_turn_request(SYSTEM, [USER, turn, RESULT], TOOLS)

    assert request["input"][1:3] == [REASONING_ITEM, CALL_ITEM]
    assert len(request["input"]) == 4


def test_a_text_turn_without_provider_items_goes_back_as_a_message() -> None:
    """Sprawdza, czy tura modelu z samym tekstem, bez elementów dostawcy, trafia do żądania jako
    wiadomość o roli `assistant` z tym tekstem.

    Wyłapuje zgubienie tekstu tury, która nie pochodzi od tego dostawcy (na przykład z atrapy):
    model nie widziałby w następnej turze własnej wcześniejszej wypowiedzi."""
    turn    = ChatMessage(role="assistant", content="Najpierw sprawdzę zgłoszenia.")
    request = make_client()._build_turn_request(SYSTEM, [USER, turn], TOOLS)

    assert request["input"][1] == {"role": "assistant", "content": "Najpierw sprawdzę zgłoszenia."}


def test_tools_go_as_function_tools_without_strict_mode() -> None:
    """Sprawdza, czy narzędzia trafiają do żądania w kolejności, w jakiej je podano, każde jako
    narzędzie typu `function` z nazwą, opisem i schematem argumentów oraz z jawnie wyłączonym
    trybem `strict`.

    Wyłapuje narzędzia w zmienionej kolejności (psuje to cache promptu u dostawcy) oraz brak pola
    `strict`: to API domyślnie włącza ten tryb i odrzuca wtedy nasze schematy."""
    request = make_client()._build_turn_request(SYSTEM, [USER], TOOLS)

    assert request["tools"] == [
        {
            "type":        "function",
            "name":        tool.name,
            "description": tool.description,
            "parameters":  tool.parameters,
            "strict":      False,
        }
        for tool in TOOLS
    ]


def test_the_turn_request_forces_a_tool_call_and_stores_nothing() -> None:
    """Sprawdza, czy żądanie tury wymusza wywołanie narzędzia, prosi dostawcę, żeby odpowiedzi nie
    przechowywał, żąda rozumowania w postaci zaszyfrowanej do odesłania i ma limit długości
    odpowiedzi.

    Wyłapuje żądanie, po którym model mógłby odpowiedzieć samym tekstem zamiast narzędziem,
    odpowiedź z danymi klienta zostawioną u dostawcy oraz brak rozumowania do odesłania, bez
    którego druga tura rozmowy nieprzechowywanej u dostawcy nie przechodzi."""
    request = make_client()._build_turn_request(SYSTEM, [USER], TOOLS)

    assert request["tool_choice"]       == "required"
    assert request["store"]             is False
    assert request["include"]           == ["reasoning.encrypted_content"]
    assert request["max_output_tokens"] > 0


@pytest.mark.parametrize(
    "model, sends_temperature",
    [("gpt-5.4-mini", True), ("gpt-6.1-sol", False)],
    ids=["accepting", "refusing"],
)
def test_the_turn_request_sends_temperature_only_where_accepted(
    model:             str,
    sends_temperature: bool,
) -> None:
    """Sprawdza, czy żądanie tury ma `temperature` tylko dla modelu z rodziny, która ten parametr
    przyjmuje (tu `gpt-5.4-mini`), a dla pozostałych (tu `gpt-6.1-sol`) go nie zawiera.

    Wyłapuje turę wysłaną z parametrem, na który nowsze modele odpowiadają błędem 400: reguła
    obowiązuje tak samo jak w zwykłym wywołaniu, a tura ma własne składanie żądania."""
    request = make_client(model)._build_turn_request(SYSTEM, [USER], TOOLS)

    assert ("temperature" in request) is sends_temperature


# --- odpowiedź ------------------------------------------------------------------------------

def test_tool_calls_are_read_with_their_arguments() -> None:
    """Sprawdza, czy z odpowiedzi z rozumowaniem i dwoma wywołaniami narzędzi klient odczytuje oba
    wywołania w kolejności: identyfikator, nazwę i argumenty zamienione z tekstu JSON na słownik.

    Wyłapuje wywołanie zgubione, w złej kolejności albo z argumentami zostawionymi jako tekst:
    węzeł wykonujący narzędzia nie miałby czego zwalidować ani wykonać."""
    response = StubResponse(output=[
        StubItem(type="reasoning", id="rs_1", summary=[], encrypted_content="gAAA…"),
        call_item("call_1", "find_tickets_vector"),
        call_item("call_2", "read_docs", '{"section_ids": ["adm-1"]}'),
    ])

    turn = make_client()._to_turn(response, elapsed_ms=3120.4)

    assert turn.message.tool_calls == [
        ToolCall(call_id="call_1", name="find_tickets_vector", arguments=SEARCH_ARGUMENTS),
        ToolCall(call_id="call_2", name="read_docs", arguments={"section_ids": ["adm-1"]}),
    ]
    assert turn.model      == MODEL
    assert turn.latency_ms == 3120.4


def test_the_whole_answer_is_kept_for_the_next_turn() -> None:
    """Sprawdza, czy tura zachowuje wszystkie elementy odpowiedzi dostawcy, w jego kolejności
    (najpierw rozumowanie, potem wywołanie), bez pól, których dostawca nie wypełnił.

    Wyłapuje turę, która gubi rozumowanie albo zmienia kolejność elementów, oraz puste pola
    odsyłane dostawcy jako `null`, które następne żądanie mogłoby odrzucić."""
    response = StubResponse(output=[
        StubItem(type="reasoning", id="rs_1", summary=[], encrypted_content="gAAA…", content=None),
        call_item("call_1"),
    ])

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert turn.message.provider_items == [
        {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "gAAA…"},
        {
            "type":      "function_call",
            "id":        "fc_call_1",
            "call_id":   "call_1",
            "name":      "find_tickets_vector",
            "arguments": json.dumps(SEARCH_ARGUMENTS, ensure_ascii=False),
            "status":    "completed",
        },
    ]


def test_a_turn_with_text_only_is_returned_as_text() -> None:
    """Sprawdza, czy odpowiedź z samym tekstem, bez wywołań narzędzi, wraca jako tura modelu z tym
    tekstem i pustą listą wywołań, a nie jako błąd.

    Wyłapuje klienta, który sam ocenia turę bez narzędzia: co zrobić z takim tekstem, rozstrzyga
    graf, więc tekst modelu ma do niego dotrzeć."""
    response = StubResponse(
        output      = [StubItem(type="message", id="msg_1", role="assistant")],
        output_text = "Nie wiem, czego szukać.",
    )

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert turn.message.content    == "Nie wiem, czego szukać."
    assert turn.message.tool_calls == []


def test_an_empty_turn_is_an_error_naming_the_reason() -> None:
    """Sprawdza, czy odpowiedź bez tekstu i bez wywołań narzędzi kończy się wyjątkiem `LLMError`,
    który podaje powód od dostawcy, tu wyczerpany limit długości odpowiedzi.

    Wyłapuje pustą turę doklejoną do rozmowy: pętla agenta szłaby dalej na odpowiedzi, której
    model nie udzielił, a wołający nie wiedziałby, że zabrakło budżetu na odpowiedź."""
    response = StubResponse(
        output            = [StubItem(type="reasoning", id="rs_1", summary=[])],
        status            = "incomplete",
        incomplete_reason = "max_output_tokens",
    )

    with pytest.raises(LLMError, match="max_output_tokens"):
        make_client()._to_turn(response, elapsed_ms=1.0)


def test_broken_arguments_stop_the_turn() -> None:
    """Sprawdza, czy wywołanie narzędzia z argumentami, które nie są poprawnym JSON-em, kończy
    turę wyjątkiem `LLMError` z nazwą narzędzia.

    Wyłapuje wywołanie przepuszczone z argumentami, których nie da się odczytać: do węzła
    narzędzi trafiłoby coś, czego nie da się ani zwalidować, ani wykonać."""
    response = StubResponse(output=[call_item(arguments='{"problem": "Brak')])

    with pytest.raises(LLMError, match="find_tickets_vector"):
        make_client()._to_turn(response, elapsed_ms=1.0)


def test_the_usage_of_the_turn_is_split_into_classes_and_priced() -> None:
    """Sprawdza, czy zużycie tury jest rozdzielone na rozłączne klasy: z 5000 tokenów wejścia,
    w których dostawca mieści 3000 odczytu z cache i 1500 zapisu, świeżego wejścia jest 500;
    do tego 200 tokenów wyjścia, jedno wywołanie i koszt policzony z cennika z tych liczb.

    Wyłapuje turę rozliczoną inaczej niż zwykłe wywołanie, na przykład z tokenami cache
    policzonymi drugi raz jako świeże wejście: koszt sprawy byłby wtedy zawyżony kilkukrotnie."""
    response = StubResponse(
        output = [call_item()],
        usage  = StubUsage(
            input_tokens       = 5000,
            output_tokens      = 200,
            cached_tokens      = 3000,
            cache_write_tokens = 1500,
        ),
    )

    usage = make_client()._to_turn(response, elapsed_ms=1.0).usage

    assert usage.calls              == 1
    assert usage.prompt_tokens      == 500
    assert usage.cache_read_tokens  == 3000
    assert usage.cache_write_tokens == 1500
    assert usage.completion_tokens  == 200
    assert usage.cost_usd           == calculate_cost_usd(
        model              = MODEL,
        prompt_tokens      = 500,
        completion_tokens  = 200,
        cache_write_tokens = 1500,
        cache_read_tokens  = 3000,
    )
    assert usage.cost_usd > 0
