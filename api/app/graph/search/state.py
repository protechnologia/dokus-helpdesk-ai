from typing import Annotated

from pydantic import Field

from app.graph.base import GraphState, merge_sources
from app.graph.search.models import SearchDone
from app.tools import SourceRef


class SearchState(GraphState):
    """
    Description:
    Stan grafu `search`: pola wspólne z `GraphState` plus źródła i sygnał końca. `input_text` to
    zgłoszenie, do którego agent szuka materiału.
    """

    sources: Annotated[list[SourceRef], merge_sources] = Field(default_factory=list)  # trafienia z `cite()`; reduktor pomija powtórzenia
    output:  SearchDone | None                         = None                         # sygnał końca; ustawia węzeł `respond`
