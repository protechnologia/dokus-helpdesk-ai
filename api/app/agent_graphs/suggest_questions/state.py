from typing import Annotated

from pydantic import Field

from app.agent_graphs.base import GraphState, merge_sources
from app.agent_tools import SourceRef
from app.core_model.graphs.proposal import Proposal
from app.core_model.graphs.proposal_notes import ProposalNotes


class SuggestQuestionsState(GraphState):
    """
    Description:
    Stan grafu `suggest_questions`: pola wspólne z `GraphState` plus źródła i propozycja.
    `input_text` to zgłoszenie z wątkiem. Gdy fakty ze zgłoszenia rozstrzygają sprawę i pytań
    już nie trzeba, `output` to same uwagi (`ProposalNotes`).
    """

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)  # trafienia z `cite()`; reduktor pomija powtórzenia
    output:  Proposal | ProposalNotes | None           = None                         # propozycja albo same uwagi; ustawia węzeł `respond`
