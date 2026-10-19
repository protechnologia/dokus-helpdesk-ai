import operator
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from anonymizer_app.core_model.found import Found
from anonymizer_app.core_model.log_entry import LogEntry


class AnonymizeState(BaseModel):
    """
    Description:
    Stan grafu anonimizacji: wejście, wynik każdego węzła i przebieg. Każde pole poza `log` pisze
    jeden węzeł, więc reduktora potrzebuje tylko `log`, do którego piszą też dwa węzły
    równoległe.

    Pole niesie surowe zgłoszenie (`input_text`) i jego fragmenty (miejsca wskazują w nim dane
    osobowe), więc stan nie trafia do logu ani do tracingu — LangSmith blokuje import pakietu
    grafów.
    """

    model_config = ConfigDict(extra="forbid")

    input_text:     str                                     = Field(min_length=1)          # surowy tekst z żądania
    after_patterns: str | None                              = None                         # tekst po wzorcach; pisze `replace_patterns`
    chunks:         list[str]                               = Field(default_factory=list)  # części tekstu po wzorcach dla modelu; pisze `split_chunks`
    persons:        list[Found]                             = Field(default_factory=list)  # miejsca imion i nazwisk w `after_patterns`; pisze `find_persons`
    addresses:      list[Found]                             = Field(default_factory=list)  # miejsca adresów w `after_patterns`; pisze `find_addresses`
    output:         str | None                              = None                         # tekst ze znacznikami; pisze `replace_found`
    log:            Annotated[list[LogEntry], operator.add] = Field(default_factory=list)  # przebieg: po wpisie od każdego węzła
