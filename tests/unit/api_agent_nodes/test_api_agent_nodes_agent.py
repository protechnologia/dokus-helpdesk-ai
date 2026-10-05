import pytest
from pydantic import BaseModel

from app.agent_graphs import GraphState
from app.agent_nodes.agent import AgentNode, tool_call_turn
from app.engine_anonymization import AnonymizedText
from app.engine_llm import ChatMessage, FakeLLMClient, LLMError, LLMUsage, ToolDefinition

# Węzeł właściwy `agent` na atrapie modelu: co wysyła modelowi w pierwszej i w kolejnych turach
# i co zapisuje w stanie grafu. Przebieg przez LangGraph sprawdzają testy integracyjne.

SYSTEM = "Jesteś asystentem wdrożeniowca helpdesku."

TOOLS = [
    ToolDefinition(name="find_tickets_vector", description="Szuka.", parameters={"type": "object"}),
    ToolDefinition(name="respond_search", description="Kończy.", parameters={"type": "object"}),
]

RAW        = "Jan Kowalski: nie przychodzą przesyłki"
ANONYMIZED = "{KLIENT_1}: nie przychodzą przesyłki"

SEARCH_ARGUMENTS = {"problem": "Brak przesyłek", "symptoms": "pusta skrzynka"}

SEARCH  = tool_call_turn("find_tickets_vector", SEARCH_ARGUMENTS)
RESPOND = tool_call_turn("respond_search", {}, call_id="call_2")
RESULT  = ChatMessage(role="tool", call_id="call_1", content='{"tickets": []}')
TEXT    = ChatMessage(role="assistant", content="Najpierw sprawdzę…")


def user_prompt(
    state: BaseModel,  # np. GraphState(input_text="…", anonymized=AnonymizedText(text="…"))
) -> str:
    """
    Description:
    Tura użytkownika na potrzeby testu — jak `user_prompt()` grafu, bierze tekst z `anonymized`.

    Example args:
        state=GraphState(input_text="Jan Kowalski…", anonymized=AnonymizedText(text="{KLIENT_1}…"))

    Example result:
        "=== ZGŁOSZENIE ===\\n{KLIENT_1}: nie przychodzą przesyłki"
    """
    return f"=== ZGŁOSZENIE ===\n{state.anonymized.text}"


def make_node(
    llm: FakeLLMClient,  # np. FakeLLMClient(turns=[SEARCH, RESPOND])
) -> AgentNode:
    """
    Description:
    Węzeł `agent` z promptem i narzędziami testu, na podanej atrapie modelu.

    Example args:
        llm=FakeLLMClient(turns=[SEARCH, RESPOND])

    Example result:
        AgentNode z dwoma narzędziami
    """
    return AgentNode(llm=llm, system_prompt=SYSTEM, user_prompt=user_prompt, tools=TOOLS)


def make_state(
    messages:   list[ChatMessage] | None = None,  # np. [ChatMessage(role="user", …), SEARCH]
    iterations: int = 0,                          # np. 1 — ile tur modelu już było
) -> GraphState:
    """
    Description:
    Stan grafu po anonimizacji, z podaną rozmową.

    Example args:
        messages=None
        iterations=0

    Example result:
        GraphState(input_text="Jan Kowalski…", anonymized=AnonymizedText(text="{KLIENT_1}…"))
    """
    state = GraphState(
        input_text = RAW,
        anonymized = AnonymizedText(text=ANONYMIZED),
        messages   = messages or [],
        iterations = iterations,
    )

    return state


async def test_the_first_turn_opens_the_conversation_with_the_user_prompt() -> None:
    """Sprawdza, czy w pierwszej turze, gdy rozmowa jest jeszcze pusta, model dostaje prompt
    systemowy, turę użytkownika złożoną z promptu grafu i narzędzia. Do stanu grafu trafia tura
    użytkownika i tura modelu, a licznik tur wynosi 1.

    Wyłapuje węzeł, który nie otwiera rozmowy zgłoszeniem albo nie zapisuje go w stanie: w kolejnych
    turach model nie wiedziałby, czego sprawa dotyczy."""
    llm  = FakeLLMClient(turns=[SEARCH])
    user = ChatMessage(role="user", content=f"=== ZGŁOSZENIE ===\n{ANONYMIZED}")

    update = await make_node(llm).run(make_state())

    assert llm.turn_calls[0].system   == SYSTEM
    assert llm.turn_calls[0].messages == [user]
    assert llm.turn_calls[0].tools    == TOOLS
    assert update["messages"]         == [user, SEARCH]
    assert update["iterations"]       == 1


async def test_the_raw_text_does_not_reach_the_model() -> None:
    """Sprawdza, czy do modelu idzie wyłącznie tekst po anonimizacji: stan niesie obie wersje
    zgłoszenia, a w wysłanej turze jest znacznik `{KLIENT_1}` i nie ma nazwiska z wersji surowej.

    Wyłapuje węzeł, który sięgnąłby po surowe zgłoszenie: dane klienta wyszłyby wtedy do
    zewnętrznego modelu."""
    llm = FakeLLMClient(turns=[SEARCH])

    await make_node(llm).run(make_state())

    sent = llm.turn_calls[0].messages[0].content

    assert ANONYMIZED         in sent
    assert "Jan Kowalski" not in sent


async def test_a_later_turn_sends_the_conversation_from_the_state() -> None:
    """Sprawdza, czy w kolejnej turze model dostaje rozmowę zapisaną w stanie grafu bez zmian i bez
    drugiej tury użytkownika. Do stanu trafia tylko nowa tura modelu, a licznik tur rośnie z 1 do 2.

    Wyłapuje węzeł, który w każdej turze dokleja zgłoszenie od nowa albo zapisuje w stanie
    wiadomości, które już tam są: rozmowa rosłaby o powtórzenia, a z nią koszt każdej tury."""
    user     = ChatMessage(role="user", content=f"=== ZGŁOSZENIE ===\n{ANONYMIZED}")
    messages = [user, SEARCH, RESULT]
    llm      = FakeLLMClient(turns=[RESPOND])

    update = await make_node(llm).run(make_state(messages, iterations=1))

    assert llm.turn_calls[0].messages == messages
    assert update["messages"]         == [RESPOND]
    assert update["iterations"]       == 2


async def test_every_turn_starts_with_the_same_prompt_and_tools() -> None:
    """Sprawdza, czy w dwóch kolejnych turach model dostaje ten sam prompt systemowy i te same
    narzędzia w tej samej kolejności.

    Wyłapuje początek żądania, który zmienia się między turami: dostawca przestałby wtedy czytać go
    z pamięci podręcznej promptu, więc każda tura kosztowałaby pełną stawkę."""
    llm   = FakeLLMClient(turns=[SEARCH, RESPOND])
    node  = make_node(llm)
    first = await node.run(make_state())

    await node.run(make_state([*first["messages"], RESULT], iterations=1))

    assert llm.turn_calls[0].system == llm.turn_calls[1].system
    assert llm.turn_calls[0].tools  == llm.turn_calls[1].tools


async def test_provider_items_go_back_to_the_model_untouched() -> None:
    """Sprawdza, czy element, który dostawca każe odesłać razem z turą modelu (tu zmyślony zapis
    rozumowania), wraca do modelu w następnej turze w tej samej wiadomości i bez zmian.

    Wyłapuje węzeł, który gubi albo przerabia ten element: prawdziwy dostawca odrzuciłby wtedy
    następną turę rozmowy."""
    reasoning = {"type": "reasoning", "id": "rs_1", "encrypted_content": "gAAAAB…"}
    thinking  = SEARCH.model_copy(update={"provider_items": [reasoning]})
    user      = ChatMessage(role="user", content="=== ZGŁOSZENIE ===")
    llm       = FakeLLMClient(turns=[RESPOND])

    await make_node(llm).run(make_state([user, thinking, RESULT], iterations=1))

    assert llm.turn_calls[0].messages[1].provider_items == [reasoning]


async def test_the_usage_of_the_turn_goes_to_the_state() -> None:
    """Sprawdza, czy węzeł oddaje do stanu zużycie modelu z tej jednej tury: jedno wywołanie,
    policzone tokeny wejścia i koszt zero, bo atrapa modelu nic nie kosztuje.

    Wyłapuje węzeł, który zużycia nie przekazuje albo sam je sumuje: sumowaniem zajmuje się stan
    grafu, więc koszt sprawy w odpowiedzi byłby zaniżony albo policzony podwójnie."""
    update = await make_node(FakeLLMClient(turns=[SEARCH])).run(make_state())

    assert isinstance(update["usage"], LLMUsage)
    assert update["usage"].calls         == 1
    assert update["usage"].prompt_tokens  > 0
    assert update["usage"].cost_usd      == 0.0


@pytest.mark.parametrize(
    "turn, message",
    [
        (SEARCH, "tura 1: narzędzia: find_tickets_vector"),
        (TEXT,   "tura 1: tekst bez narzędzi"),
    ],
    ids=["tool-call", "text-only"],
)
async def test_the_log_names_tools_and_quotes_nothing(turn: ChatMessage, message: str) -> None:
    """Sprawdza, czy po turze modelu w dzienniku przebiegu jest dokładnie jeden wpis węzła `agent`:
    z nazwą wywołanego narzędzia albo z informacją, że model odpowiedział samym tekstem.

    Wyłapuje wpis, który cytuje argumenty wywołania albo tekst modelu: to dane klienta, a dziennik
    wraca do wołającego razem z odpowiedzią."""
    update = await make_node(FakeLLMClient(turns=[turn])).run(make_state())

    assert [(entry.node, entry.message) for entry in update["log"]] == [("agent", message)]


async def test_a_failed_model_call_stops_the_node() -> None:
    """Sprawdza, czy błąd modelu (`LLMError`) wychodzi z węzła bez przechwycenia. Awarię udaje tu
    atrapa modelu, której przy drugim wywołaniu skończyły się zaplanowane tury.

    Wyłapuje węzeł, który połyka błąd modelu i jedzie dalej: przebieg ma się zatrzymać, a trasa
    oddać 503, zamiast zgadywać odpowiedź."""
    node = make_node(FakeLLMClient(turns=[SEARCH]))

    await node.run(make_state())

    with pytest.raises(LLMError):
        await node.run(make_state())


def test_a_node_without_tools_is_refused() -> None:
    """Sprawdza, czy węzła `agent` nie da się zbudować z pustą listą narzędzi: kończy się to błędem
    już przy budowie.

    Wyłapuje źle złożony graf: każdy graf odpowiada wywołaniem narzędzia odpowiedzi, więc model bez
    narzędzi nie miałby czym odpowiedzieć, a wyszłoby to dopiero w trakcie żądania."""
    with pytest.raises(ValueError, match="bez narzędzi"):
        AgentNode(llm=FakeLLMClient(), system_prompt=SYSTEM, user_prompt=user_prompt, tools=[])
