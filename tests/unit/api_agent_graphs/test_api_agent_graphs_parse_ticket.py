from app.agent_graphs.parse_ticket import FILLED_BY_GRAPH, example_state, respond_tool, user_prompt
from app.agent_graphs.parse_ticket.graph import build_parse_prompt
from app.anonymization import AnonymizedText


def test_the_graph_prompt_is_the_parsing_prompt_with_the_anonymized_thread() -> None:
    """Tura użytkownika grafu → prompt parsujący z wątkiem po anonimizacji i słownikiem ze stanu."""
    state = example_state().model_copy(update={"anonymized": AnonymizedText(text="ZGŁOSZENIE 1")})

    assert user_prompt(state) == build_parse_prompt("ZGŁOSZENIE 1", state.vocabulary)


def test_the_model_is_not_asked_for_what_the_graph_fills() -> None:
    """Pola tożsamości, daty i wersji słownika → poza schematem narzędzia odpowiedzi: model, który
    by je wymyślił, nie ma jak ich podać, a graf bierze je ze stanu."""
    assert not set(FILLED_BY_GRAPH) & set(respond_tool().parameters["properties"])
