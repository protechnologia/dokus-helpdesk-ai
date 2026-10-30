from app.agent_graphs import suggest_handoff
from app.agent_nodes.agent import tool_call_turn
from app.core_model.graphs.proposal import Proposal

# Odpowiedź modelu w grafie `suggest_handoff`: model podaje sam tekst, a uwagi wypełnia graf.
# Kształt grafu, narzędzia i zabezpieczenia wspólne dla wszystkich grafów sprawdza test kontraktu
# grafów.

# Tekst przekazania sprawy, jakim odpowiada model.
TEXT = "Dzień dobry, nie działa podpis. Sprawę przekazujemy do dalszych prac po stronie serwisu."


async def test_a_text_only_answer_becomes_a_proposal_with_empty_notes() -> None:
    """Sprawdza, czy odpowiedź modelu z samym tekstem daje propozycję z tym tekstem i pustymi
    uwagami.

    Wyłapuje węzeł, który nie dokłada uwag od grafu: każda poprawna odpowiedź modelu wracałaby
    wtedy do poprawki z błędem brakującego pola, a wariant kończyłby się awarią."""
    turn  = tool_call_turn(suggest_handoff.RESPOND_TOOL_NAME, {"text": TEXT})
    state = suggest_handoff.example_state().model_copy(update={"messages": [turn]})

    update = await suggest_handoff.respond_node().run(state)

    assert update["output"] == Proposal(text=TEXT, internal_notes="")


async def test_notes_from_the_model_do_not_reach_the_result() -> None:
    """Sprawdza, czy uwagi dopisane przez model mimo schematu nie trafiają do wyniku.

    Wyłapuje pole od grafu, które przegrywa z argumentami modelu: helpdesk dostałby wtedy uwagi,
    których ten wariant nie ma, napisane bez żadnej nowej wiedzy poza wątkiem."""
    arguments = {"text": TEXT, "internal_notes": "Sprawdzić logi kolejki."}
    turn      = tool_call_turn(suggest_handoff.RESPOND_TOOL_NAME, arguments)
    state     = suggest_handoff.example_state().model_copy(update={"messages": [turn]})

    update = await suggest_handoff.respond_node().run(state)

    assert update["output"].internal_notes == ""
