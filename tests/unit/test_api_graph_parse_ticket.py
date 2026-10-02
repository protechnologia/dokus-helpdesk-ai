from app.anonymization import AnonymizedText
from app.graph.parse_ticket import (
    ParseTicketState,
    build_fake_graph,
    example_state,
    model_tools,
    system_prompt,
    user_prompt,
)
from app.model.ticket_parsed import ParsedTicket
from app.service.prompt_ticket_parse import build_parse_prompt
from app.service.prompt_ticket_parse import system_prompt as parse_system_prompt


def test_the_graph_uses_the_parsing_prompt_of_the_corpus() -> None:
    """Prompty grafu → ten sam prompt parsujący co korpus, z wątkiem po anonimizacji i słownikiem
    ze stanu: karta z runtime i artefakt z masowego importu powstają jednym kontraktem."""
    state = example_state().model_copy(update={"anonymized": AnonymizedText(text="ZGŁOSZENIE 1")})

    assert system_prompt()    == parse_system_prompt()
    assert user_prompt(state) == build_parse_prompt("ZGŁOSZENIE 1", state.vocabulary)


def test_the_model_gets_no_tools_at_all() -> None:
    """Definicje narzędzi → pusta lista, także bez narzędzia odpowiedzi: prompt parsujący każe
    zwrócić JSON w tekście (do rozstrzygnięcia w p. 24)."""
    assert model_tools([]) == []


async def test_the_fake_agent_answers_with_json_text() -> None:
    """Atrapa → ostatnia tura agenta to tekst, który waliduje się do karty z `output`."""
    state = ParseTicketState(**await build_fake_graph().ainvoke(example_state()))

    assert state.messages[-1].tool_calls                               == []
    assert ParsedTicket.model_validate_json(state.messages[-1].content) == state.output
