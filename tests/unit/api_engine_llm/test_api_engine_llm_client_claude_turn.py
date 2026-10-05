import pytest

from app.engine_llm import ChatMessage, LLMError, ToolCall, ToolDefinition
from app.engine_llm.client.claude import ClaudeLLMClient
from app.engine_llm.pricing.claude import calculate_cost_usd

# Tura z narzędziami w kliencie Claude'a (Messages API): jak rozmowa i narzędzia stają się
# żądaniem i jak odpowiedź dostawcy staje się turą modelu. Bez sieci — testy wołają
# `_build_turn_request()` i `_to_turn()` wprost. Na żywym API tura Claude'a nie była sprawdzana.

API_KEY = "sk-ant-test-key"
MODEL   = "claude-sonnet-5"

# Model z rodziny, która nadal przyjmuje `temperature`.
MODEL_WITH_TEMPERATURE = "claude-haiku-4-5"

SYSTEM = "Jesteś asystentem wdrożeniowca helpdesku."

USER = ChatMessage(role="user", content="Nie przychodzą przesyłki z e-Doręczeń")

TOOLS = [
    ToolDefinition(
        name        = "read_tickets_card",
        description = "Czyta karty.",
        parameters  = {"type": "object", "properties": {"ticket_ids": {"type": "array"}}},
    ),
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]


class StubBlock:
    """
    Description:
    Jeden blok odpowiedzi Messages API w atrapie: pola dostępne jak atrybuty i `model_dump()`
    oddający je jako słownik, tak jak modele SDK.
    """

    def __init__(
        self,
        **fields,  # np. type="tool_use", id="toolu_1", name="read_docs", input={"section_ids": […]}
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
        Oddaje pola bloku jako słownik; z `exclude_none` bez pól pustych.

        Example args:
            mode="json"
            exclude_none=True

        Example result:
            {"type": "server_tool_use", "id": "srv_1", "name": "web_search"}
        """
        return {
            name: value
            for name, value in self._fields.items()
            if not (exclude_none and value is None)
        }


class StubUsage:
    """
    Description:
    Liczniki zużycia w atrapie odpowiedzi. W tym API klasy tokenów są rozłączne od razu.
    """

    def __init__(
        self,
        input_tokens:                int,      # np. 4820 — samo świeże wejście
        output_tokens:               int,      # np. 640
        cache_creation_input_tokens: int = 0,  # np. 1830
        cache_read_input_tokens:     int = 0,  # np. 1830
    ):
        self.input_tokens                = input_tokens
        self.output_tokens               = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens     = cache_read_input_tokens


class StubResponse:
    """
    Description:
    Jedna atrapa odpowiedzi Messages API na turę z narzędziami, z tym, co klient czyta.
    """

    def __init__(
        self,
        blocks:      list[StubBlock],          # np. [StubBlock(type="tool_use", …)]
        usage:       StubUsage | None = None,
        stop_reason: str = "tool_use",         # np. "max_tokens"
    ):
        self.content     = blocks
        self.usage       = usage or StubUsage(input_tokens=100, output_tokens=10)
        self.model       = MODEL
        self.stop_reason = stop_reason


def make_client(
    model: str = MODEL,  # np. "claude-haiku-4-5"
) -> ClaudeLLMClient:
    """
    Description:
    Buduje klienta z atrapą klucza. Nic tu nie sięga do sieci.

    Example args:
        model="claude-haiku-4-5"

    Example result:
        ClaudeLLMClient(model="claude-haiku-4-5")
    """
    return ClaudeLLMClient(api_key=API_KEY, model=model, temperature=0.0)


def tool_use(
    block_id: str    = "toolu_1",            # np. "toolu_2"
    name:     str    = "read_tickets_card",  # np. "read_docs"
    args:     object = None,                 # np. {"ticket_ids": ["90001"]}
) -> StubBlock:
    """
    Description:
    Blok wywołania narzędzia w kształcie, w jakim oddaje go dostawca, z polem `caller`, którego
    żądanie nie przyjmuje z powrotem.

    Example args:
        block_id="toolu_1"
        name="read_tickets_card"
        args={"ticket_ids": ["90001"]}

    Example result:
        StubBlock(type="tool_use", id="toolu_1", name="read_tickets_card", input={…}, caller={…})
    """
    return StubBlock(
        type   = "tool_use",
        id     = block_id,
        name   = name,
        input  = args if args is not None else {"ticket_ids": ["90001"]},
        caller = {"type": "direct"},
    )


# --- żądanie --------------------------------------------------------------------------------

def test_the_results_of_one_turn_go_back_in_one_user_message() -> None:
    """Sprawdza, czy rozmowa z turą modelu, która wywołała dwa narzędzia, i z dwoma wynikami staje
    się trzema wiadomościami: pytanie użytkownika, tura modelu z dwoma blokami `tool_use` i JEDNA
    wiadomość użytkownika z dwoma blokami `tool_result`, każdy ze wskazaniem swojego wywołania.
    Prompt systemowy idzie osobno, w polu `system`.

    Wyłapuje wyniki narzędzi rozbite na osobne wiadomości albo wysłane pod rolą, której to API
    nie zna: dostawca odrzuca rozmowę, w której wyniki nie stoją razem zaraz po turze modelu."""
    turn = ChatMessage(
        role       = "assistant",
        content    = "Przeczytam oba.",
        tool_calls = [
            ToolCall(call_id="toolu_1", name="read_tickets_card", arguments={"ticket_ids": ["1"]}),
            ToolCall(call_id="toolu_2", name="read_tickets_card", arguments={"ticket_ids": ["2"]}),
        ],
    )
    results = [
        ChatMessage(role="tool", call_id="toolu_1", content='{"cards": [1]}'),
        ChatMessage(role="tool", call_id="toolu_2", content='{"cards": [2]}'),
    ]

    request = make_client()._build_turn_request(SYSTEM, [USER, turn, *results], TOOLS)

    assert request["system"]   == SYSTEM
    assert request["messages"] == [
        {"role": "user", "content": USER.content},
        {
            "role":    "assistant",
            "content": [
                {"type": "text", "text": "Przeczytam oba."},
                {"type": "tool_use", "id": "toolu_1", "name": "read_tickets_card",
                 "input": {"ticket_ids": ["1"]}},
                {"type": "tool_use", "id": "toolu_2", "name": "read_tickets_card",
                 "input": {"ticket_ids": ["2"]}},
            ],
        },
        {
            "role":    "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"cards": [1]}'},
                {"type": "tool_result", "tool_use_id": "toolu_2", "content": '{"cards": [2]}'},
            ],
        },
    ]


def test_the_results_of_two_turns_stay_in_two_messages() -> None:
    """Sprawdza, czy wyniki narzędzi z dwóch kolejnych tur modelu trafiają do dwóch osobnych
    wiadomości użytkownika, każda zaraz po swojej turze.

    Wyłapuje sklejanie wyników, które sięga za daleko: wynik z drugiej tury dopisany do
    wiadomości z pierwszej stałby przed wywołaniem, na które odpowiada."""
    first  = ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="toolu_1", name="a")])
    second = ChatMessage(role="assistant", tool_calls=[ToolCall(call_id="toolu_2", name="b")])
    done_1 = ChatMessage(role="tool", call_id="toolu_1", content="{}")
    done_2 = ChatMessage(role="tool", call_id="toolu_2", content="{}")

    messages = make_client()._build_turn_request(
        SYSTEM, [USER, first, done_1, second, done_2], TOOLS,
    )["messages"]

    assert [message["role"] for message in messages] == [
        "user", "assistant", "user", "assistant", "user",
    ]
    assert [block["tool_use_id"] for block in messages[2]["content"]] == ["toolu_1"]
    assert [block["tool_use_id"] for block in messages[4]["content"]] == ["toolu_2"]


def test_a_turn_of_this_provider_goes_back_with_its_own_blocks() -> None:
    """Sprawdza, czy tura modelu, która niesie bloki oddane przez dostawcę (myślenie z podpisem
    i wywołanie narzędzia), wraca do niego dokładnie tymi blokami, w tej samej kolejności.

    Wyłapuje turę odesłaną bez bloku myślenia albo z blokami złożonymi od nowa z naszych pól:
    dostawca sprawdza podpis myślenia i odrzuca rozmowę, w której go brakuje albo coś zmieniono."""
    blocks = [
        {"type": "thinking", "thinking": "Sprawdzę kartę.", "signature": "sig-abc"},
        {"type": "tool_use", "id": "toolu_1", "name": "read_tickets_card",
         "input": {"ticket_ids": ["90001"]}},
    ]
    turn = ChatMessage(
        role           = "assistant",
        tool_calls     = [ToolCall(call_id="toolu_1", name="read_tickets_card")],
        provider_items = blocks,
    )

    messages = make_client()._build_turn_request(SYSTEM, [USER, turn], TOOLS)["messages"]

    assert messages[1] == {"role": "assistant", "content": blocks}


def test_tools_go_with_their_schema_and_a_tool_call_is_forced() -> None:
    """Sprawdza, czy narzędzia trafiają do żądania w kolejności, w jakiej je podano, ze schematem
    argumentów pod nazwą `input_schema`, a żądanie wymusza wywołanie któregoś narzędzia, ma
    włączony cache promptu i limit długości odpowiedzi.

    Wyłapuje schemat wysłany pod nazwą z innego API, narzędzia w zmienionej kolejności (psuje to
    cache promptu) oraz żądanie, po którym model mógłby odpowiedzieć samym tekstem."""
    request = make_client()._build_turn_request(SYSTEM, [USER], TOOLS)

    assert request["tools"] == [
        {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
        for tool in TOOLS
    ]
    assert request["tool_choice"]   == {"type": "any"}
    assert request["cache_control"] == {"type": "ephemeral"}
    assert request["max_tokens"]    > 0


@pytest.mark.parametrize(
    "model, sends_temperature",
    [(MODEL_WITH_TEMPERATURE, True), (MODEL, False)],
    ids=["accepting", "refusing"],
)
def test_the_turn_request_sends_temperature_only_where_accepted(
    model:             str,
    sends_temperature: bool,
) -> None:
    """Sprawdza, czy żądanie tury ma `temperature` tylko dla modelu z rodziny, która ten parametr
    przyjmuje (tu `claude-haiku-4-5`), a dla pozostałych (tu `claude-sonnet-5`) go nie zawiera.

    Wyłapuje turę wysłaną z parametrem, na który nowsze modele odpowiadają błędem 400: reguła
    obowiązuje tak samo jak w zwykłym wywołaniu, a tura ma własne składanie żądania."""
    request = make_client(model)._build_turn_request(SYSTEM, [USER], TOOLS)

    assert ("temperature" in request) is sends_temperature


# --- odpowiedź ------------------------------------------------------------------------------

def test_tool_calls_and_text_are_read_from_the_blocks() -> None:
    """Sprawdza, czy z odpowiedzi z blokiem myślenia, tekstem i dwoma wywołaniami narzędzi klient
    odczytuje tekst modelu oraz oba wywołania w kolejności: identyfikator, nazwę i argumenty.

    Wyłapuje wywołanie zgubione albo w złej kolejności oraz myślenie modelu wzięte za jego
    odpowiedź."""
    response = StubResponse([
        StubBlock(type="thinking", thinking="Sprawdzę obie karty.", signature="sig-abc"),
        StubBlock(type="text", text="Czytam karty.", citations=None),
        tool_use("toolu_1", args={"ticket_ids": ["90001"]}),
        tool_use("toolu_2", args={"ticket_ids": ["90002"]}),
    ])

    turn = make_client()._to_turn(response, elapsed_ms=3120.4)

    assert turn.message.content    == "Czytam karty."
    assert turn.message.tool_calls == [
        ToolCall(call_id="toolu_1", name="read_tickets_card", arguments={"ticket_ids": ["90001"]}),
        ToolCall(call_id="toolu_2", name="read_tickets_card", arguments={"ticket_ids": ["90002"]}),
    ]
    assert turn.model      == MODEL
    assert turn.latency_ms == 3120.4


def test_blocks_are_kept_in_the_shape_the_provider_takes_back() -> None:
    """Sprawdza, czy tura zachowuje bloki odpowiedzi w kolejności dostawcy i w kształcie, jaki
    przyjmuje on w następnym żądaniu: myślenie z podpisem, tekst bez dodatkowych pól, wywołanie
    narzędzia bez pola `caller`, ukryte myślenie z danymi, a blok nieznanego rodzaju w całości,
    bez pól pustych.

    Wyłapuje bloki odesłane z polami, które niesie tylko odpowiedź, oraz zgubiony podpis
    myślenia: w obu przypadkach dostawca odrzuca następną turę."""
    response = StubResponse([
        StubBlock(type="thinking", thinking="Sprawdzę kartę.", signature="sig-abc"),
        StubBlock(type="redacted_thinking", data="zaszyfrowane"),
        StubBlock(type="text", text="Czytam kartę.", citations=None),
        tool_use("toolu_1", args={"ticket_ids": ["90001"]}),
        StubBlock(type="server_tool_use", id="srv_1", name="web_search", caller=None),
    ])

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert turn.message.provider_items == [
        {"type": "thinking", "thinking": "Sprawdzę kartę.", "signature": "sig-abc"},
        {"type": "redacted_thinking", "data": "zaszyfrowane"},
        {"type": "text", "text": "Czytam kartę."},
        {"type": "tool_use", "id": "toolu_1", "name": "read_tickets_card",
         "input": {"ticket_ids": ["90001"]}},
        {"type": "server_tool_use", "id": "srv_1", "name": "web_search"},
    ]


def test_a_turn_with_text_only_is_returned_as_text() -> None:
    """Sprawdza, czy odpowiedź z samym tekstem, bez wywołań narzędzi, wraca jako tura modelu z tym
    tekstem i pustą listą wywołań, a nie jako błąd.

    Wyłapuje klienta, który sam ocenia turę bez narzędzia: co zrobić z takim tekstem, rozstrzyga
    graf, więc tekst modelu ma do niego dotrzeć."""
    response = StubResponse(
        [StubBlock(type="text", text="Nie wiem, czego szukać.")],
        stop_reason = "end_turn",
    )

    turn = make_client()._to_turn(response, elapsed_ms=1.0)

    assert turn.message.content    == "Nie wiem, czego szukać."
    assert turn.message.tool_calls == []


def test_an_empty_turn_is_an_error_naming_the_stop_reason() -> None:
    """Sprawdza, czy odpowiedź bez tekstu i bez wywołań narzędzi kończy się wyjątkiem `LLMError`,
    który podaje powód zakończenia od dostawcy, tu wyczerpany limit długości odpowiedzi.

    Wyłapuje pustą turę doklejoną do rozmowy: pętla agenta szłaby dalej na odpowiedzi, której
    model nie udzielił."""
    response = StubResponse(
        [StubBlock(type="thinking", thinking="…", signature="sig")],
        stop_reason = "max_tokens",
    )

    with pytest.raises(LLMError, match="max_tokens"):
        make_client()._to_turn(response, elapsed_ms=1.0)


def test_arguments_that_are_not_an_object_stop_the_turn() -> None:
    """Sprawdza, czy wywołanie narzędzia, którego argumenty nie są obiektem (tu lista), kończy
    turę wyjątkiem `LLMError` z nazwą narzędzia.

    Wyłapuje wywołanie przepuszczone z argumentami, których nie da się zapisać w naszym kształcie:
    do węzła narzędzi trafiłoby coś, czego nie da się zwalidować."""
    response = StubResponse([tool_use(args=["90001"])])

    with pytest.raises(LLMError, match="read_tickets_card"):
        make_client()._to_turn(response, elapsed_ms=1.0)


def test_the_usage_of_the_turn_is_read_in_four_classes_and_priced() -> None:
    """Sprawdza, czy zużycie tury trafia do czterech klas tokenów bez przeliczania (świeże wejście
    4820, zapis do cache 1000, odczyt z cache 3000, wyjście 640), z jednym wywołaniem i kosztem
    policzonym z cennika z tych liczb.

    Wyłapuje turę rozliczoną inaczej niż zwykłe wywołanie albo z pominiętymi licznikami cache:
    w pętli z narzędziami większość wejścia to odczyt z cache, więc koszt sprawy byłby błędny."""
    response = StubResponse(
        [tool_use()],
        usage = StubUsage(
            input_tokens                = 4820,
            output_tokens               = 640,
            cache_creation_input_tokens = 1000,
            cache_read_input_tokens     = 3000,
        ),
    )

    usage = make_client()._to_turn(response, elapsed_ms=1.0).usage

    assert usage.calls              == 1
    assert usage.prompt_tokens      == 4820
    assert usage.cache_write_tokens == 1000
    assert usage.cache_read_tokens  == 3000
    assert usage.completion_tokens  == 640
    assert usage.cost_usd           == calculate_cost_usd(
        model              = MODEL,
        prompt_tokens      = 4820,
        completion_tokens  = 640,
        cache_write_tokens = 1000,
        cache_read_tokens  = 3000,
    )
    assert usage.cost_usd > 0
