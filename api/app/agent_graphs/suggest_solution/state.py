from typing import Annotated

from pydantic import Field

from app.agent_graphs.base import GraphState, merge_sources
from app.agent_tools import SourceRef
from app.core_model.suggest_proposal import Proposal


class SuggestSolutionState(GraphState):
    """
    Description:
    Stan grafu `suggest_solution`: pola wspólne z `GraphState` plus źródła i propozycja. `input_text` to
    zgłoszenie z wątkiem.
    """

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)  # trafienia z `cite()`; reduktor pomija powtórzenia
    output:  Proposal | None                           = None                         # propozycja; ustawia węzeł `respond`
