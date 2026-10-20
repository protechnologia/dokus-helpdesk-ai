from app.agent_graphs import ToolCallRun, graph_step
from app.engine_anonymization import AnonymizedText
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


def test_a_model_turn_names_the_tools_it_asked_for() -> None:
    """Sprawdza, czy krok tury modelu niesie nazwy narzędzi, o które model w niej poprosił
    (odczyt kart z drugiej tury), a nie narzędzi z wcześniejszej tury rozmowy.

    Wyłapuje krok tury bez tych nazw albo z nazwami wziętymi z całej rozmowy: konsola przebiegu
    nie powiedziałaby, czy po turze trwają narzędzia, czy odpowiedź, albo pokazałaby wyszukanie
    z pierwszej tury jako zlecone w drugiej."""
    step = graph_step("agent", agent_update(), two_turns()[:4], STEP_STARTED_AT, 2140.6)

    assert step.requested_tools == ["read_tickets_card"]


def test_a_tool_step_repeats_no_requested_tools() -> None:
    """Sprawdza, czy krok narzędzi nie ma nazw zleconych narzędzi, choć ostatnia tura rozmowy je
    zleca: mówi o nich krok tury, a krok narzędzi niesie ich wykonanie.

    Wyłapuje nazwy brane z ostatniej tury rozmowy zamiast ze zmiany stanu kroku: po kroku
    narzędzi konsola uznałaby, że narzędzia nadal trwają."""
    step = graph_step("run_tools", run_tools_update(), two_turns(), STEP_STARTED_AT, 85.0)

    assert step.requested_tools == []


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


def test_only_the_anonymize_step_carries_the_anonymized_text() -> None:
    """Sprawdza, czy krok `anonymize` niesie tekst ze zmiany stanu węzła — tekst po anonimizacji —
    a krok tury modelu i krok narzędzi tekstu nie niosą.

    Wyłapuje krok bez tekstu po anonimizacji albo tekst doklejany do każdego kroku: front nie
    pokazałby, co dostał model, albo strumień niósłby zgłoszenie przy każdym kroku."""
    update = {"anonymized": AnonymizedText(text="{IMIĘ} zgłasza brak przesyłek")}

    anonymize = graph_step("anonymize", update, [], STEP_STARTED_AT, 812.0)
    agent     = graph_step("agent", agent_update(), two_turns()[:4], STEP_STARTED_AT, 2140.6)
    tools     = graph_step("run_tools", run_tools_update(), two_turns(), STEP_STARTED_AT, 85.0)

    assert anonymize.anonymized_text == "{IMIĘ} zgłasza brak przesyłek"
    assert (agent.anonymized_text, tools.anonymized_text) == (None, None)
