from datetime import date as Date

from pydantic import Field

from app.agent_graphs.base import GraphState
from app.model.dict_resolution_vocabulary import ResolutionVocabulary
from app.model.ticket_parsed import ParsedTicket


class ParseTicketState(GraphState):
    """
    Description:
    Stan grafu `parse_ticket`: pola wspólne z `GraphState` plus tożsamość zgłoszenia, słownik
    rozstrzygnięć i karta. `input_text` to wątek w formacie czytnika („ZGŁOSZENIE 33644\nTemat:…").

    Tożsamość, data i słownik przychodzą w stanie, nie od modelu: to pola `FILLED_BY_GRAPH`, o które
    model nie jest pytany, a karta zapisuje wersję słownika w `resolution_vocabulary_version`
    (zasada 7). Węzeł `respond` dokłada je do argumentów `respond_parse_ticket`.
    """

    ticket_id:  str                  = Field(min_length=1)  # id zgłoszenia ze źródła
    date:       Date                                         # data zgłoszenia ze źródła
    vocabulary: ResolutionVocabulary                         # słownik rozstrzygnięć: dane klienta, do promptu parsującego
    output:     ParsedTicket | None  = None                  # karta zgłoszenia; ustawia węzeł `respond`
