from app.agent_graphs.parse_ticket import FILLED_BY_GRAPH, example_state, respond_tool, user_prompt
from app.agent_graphs.parse_ticket.graph import build_parse_prompt
from app.engine_anonymization import AnonymizedText


def test_the_graph_prompt_is_the_parsing_prompt_with_the_anonymized_thread() -> None:
    """Sprawdza, czy tura użytkownika grafu parsującego to prompt parsujący zbudowany z wątku po
    anonimizacji (tu „ZGŁOSZENIE 1") i ze słownika rozstrzygnięć zapisanego w stanie grafu.

    Wyłapuje graf, który składa turę użytkownika inaczej niż funkcja budująca prompt parsujący albo
    bierze wątek czy słownik z innego miejsca: karty zgłoszeń powstawałyby wtedy innym promptem niż
    ten, którego pilnuje test-strażnik."""
    state = example_state().model_copy(update={"anonymized": AnonymizedText(text="ZGŁOSZENIE 1")})

    assert user_prompt(state) == build_parse_prompt("ZGŁOSZENIE 1", state.vocabulary)


def test_the_model_is_not_asked_for_what_the_graph_fills() -> None:
    """Sprawdza, czy schemat narzędzia odpowiedzi grafu parsującego nie ma pól, które wypełnia graf:
    numeru zgłoszenia, daty i wersji słownika rozstrzygnięć.

    Wyłapuje schemat, w którym model mógłby te pola podać, czyli je wymyślić: mają pochodzić ze
    stanu grafu, a nie z odpowiedzi modelu."""
    assert not set(FILLED_BY_GRAPH) & set(respond_tool().parameters["properties"])
