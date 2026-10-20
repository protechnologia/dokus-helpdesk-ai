from app.entry_routers.mapping import to_step_item
from tests._helpers.routers.samples import AGENT_STEP, STEP_STARTED_AT, TOOL_STEP, USAGE


def test_a_tool_step_goes_out_with_its_calls() -> None:
    """Sprawdza, czy krok narzędzi wychodzi w zdarzeniu z wywołaniem pole po polu: identyfikator,
    narzędzie, argumenty, wynik, który dostał model, i początek wywołania.

    Wyłapuje mapowanie, które gubi albo przestawia pole wywołania: konsola przebiegu nie
    pokazałaby, o co agent pytał narzędzie i co dostał w odpowiedzi."""
    [call] = to_step_item(TOOL_STEP).tool_calls
    [run]  = TOOL_STEP.tool_calls

    assert call.call_id    == run.call_id
    assert call.tool       == run.tool
    assert call.arguments  == run.arguments
    assert call.result     == run.result
    assert call.started_at == run.started_at


def test_durations_go_out_rounded_to_a_tenth_of_a_millisecond() -> None:
    """Sprawdza, czy czas trwania kroku (85,04 ms) i wywołania (84,26 ms) wychodzi zaokrąglony do
    dziesiątych części milisekundy: 85,0 i 84,3.

    Wyłapuje czasy oddane z ogonem pomiaru albo zaokrąglone do całych sekund: pierwsze zaśmieca
    konsolę przebiegu, drugie zeruje krótkie kroki."""
    item = to_step_item(TOOL_STEP)

    assert item.duration_ms               == 85.0
    assert item.tool_calls[0].duration_ms == 84.3


def test_the_log_entries_of_a_step_become_one_message() -> None:
    """Sprawdza, czy wpisy logu kroku wychodzą jako jeden tekst, po kolei, rozdzielone średnikiem,
    a krok ma nazwę węzła i początek z przebiegu.

    Wyłapuje zdarzenie z samym pierwszym wpisem albo z wpisami w innej kolejności: konsola
    przebiegu pokazałaby niepełny opis kroku."""
    item = to_step_item(TOOL_STEP)

    assert item.message    == "wywołania: read_tickets_card; źródła: 1; drugi wpis"
    assert item.node       == "run_tools"
    assert item.started_at == STEP_STARTED_AT


def test_only_a_model_turn_goes_out_with_usage() -> None:
    """Sprawdza, czy krok tury modelu wychodzi ze zużyciem tej tury, a krok narzędzi bez zużycia
    (`None`), a nie z zerami.

    Wyłapuje zużycie zgubione przy turze albo zera przy kroku bez modelu: konsola przebiegu
    pokazałaby turę za darmo albo krok narzędzi jako wywołanie modelu."""
    agent = to_step_item(AGENT_STEP)
    tools = to_step_item(TOOL_STEP)

    assert agent.usage.llm_calls     == USAGE.calls
    assert agent.usage.prompt_tokens == USAGE.prompt_tokens
    assert tools.usage is None


def test_a_model_turn_goes_out_with_the_tools_it_asked_for() -> None:
    """Sprawdza, czy krok tury modelu wychodzi z nazwami narzędzi, o które model poprosił,
    a krok narzędzi z pustą listą.

    Wyłapuje nazwy zgubione w mapowaniu: front nie powiedziałby, co trwa po turze modelu, i
    musiałby czytać wpis logu, który jest tekstem dla człowieka."""
    agent = to_step_item(AGENT_STEP)
    tools = to_step_item(TOOL_STEP)

    assert agent.requested_tools == ["read_tickets_card"]
    assert tools.requested_tools == []
