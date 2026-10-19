from app.agent_graphs import ToolCallRun, graph_step
from tests._helpers.graphs.samples import (
    READ_RESULT,
    READ_TIMING,
    SECOND_TURN,
    STEP_STARTED_AT,
    STEP_USAGE,
    agent_update,
    run_tools_update,
    two_turns,
)


def test_a_tool_step_pairs_each_call_with_its_result_and_timing() -> None:
    """Sprawdza, czy krok narzędzi łączy pomiar czasu z wywołaniem z ostatniej tury modelu
    i z wynikiem, który dostał model: odczyt kart z drugiej tury, z jego argumentami, wynikiem,
    początkiem i czasem trwania, choć wyszukanie z pierwszej tury ma ten sam identyfikator.

    Wyłapuje łączenie po identyfikatorze w całej rozmowie: atrapa modelu numeruje wywołania od
    nowa w każdej turze, więc konsola przebiegu pokazałaby przy odczycie nazwę i argumenty
    wyszukania z poprzedniej tury."""
    step = graph_step("run_tools", run_tools_update(), two_turns(), STEP_STARTED_AT, 85.0)

    assert step.tool_calls == [
        ToolCallRun(
            call_id     = "call_1",
            tool        = "read_tickets_card",
            arguments   = SECOND_TURN.tool_calls[0].arguments,
            result      = READ_RESULT,
            started_at  = READ_TIMING.started_at,
            duration_ms = READ_TIMING.duration_ms,
        ),
    ]


def test_a_model_turn_carries_its_usage_and_no_tool_calls() -> None:
    """Sprawdza, czy krok tury modelu niesie zużycie tej tury, a wywołań narzędzi nie ma, choć
    tura je zleca: wykonuje je dopiero następny krok.

    Wyłapuje krok tury modelu bez zużycia albo z wywołaniami zleconymi zamiast wykonanych: koszt
    tury zniknąłby z konsoli przebiegu, a wywołania pokazałyby się dwa razy, raz bez wyniku."""
    step = graph_step("agent", agent_update(), two_turns()[:4], STEP_STARTED_AT, 2140.6)

    assert step.usage      == STEP_USAGE
    assert step.tool_calls == []


def test_a_step_carries_its_node_times_and_log() -> None:
    """Sprawdza, czy krok niesie nazwę węzła, podany początek i czas trwania oraz wpisy logu
    ze zmiany stanu, a krok bez tury modelu nie ma zużycia.

    Wyłapuje krok, który gubi któreś z tych pól albo przypisuje krokowi narzędzi zużycie: konsola
    przebiegu nie pokazałaby, który węzeł co zrobił i kiedy."""
    update = run_tools_update()

    step = graph_step("run_tools", update, two_turns(), STEP_STARTED_AT, 85.0)

    assert step.node        == "run_tools"
    assert step.started_at  == STEP_STARTED_AT
    assert step.duration_ms == 85.0
    assert step.log         == update["log"]
    assert step.usage       is None
