from app.graph.base import GraphState
from app.model.suggest_proposal import Proposal


class SuggestHandoffState(GraphState):
    """
    Description:
    Stan grafu `suggest_handoff`: pola wspólne z `GraphState` plus propozycja. `input_text` to
    zgłoszenie z wątkiem.

    Bez `sources` — przekazanie opiera się na tym, co sprawdzono w wątku, nie na bazie, więc
    wraca z pustą listą źródeł (CLAUDE.md -> „Generacja propozycji odpowiedzi").
    """

    output: Proposal | None = None  # propozycja przekazania; ustawia węzeł `respond`
