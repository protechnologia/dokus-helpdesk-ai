from app.graph.base import GraphState
from app.model.dict_resolution_vocabulary import ResolutionVocabulary
from app.model.ticket_parsed import ParsedTicket


class ParseTicketState(GraphState):
    """
    Description:
    Stan grafu `parse_ticket`: pola wspólne z `GraphState` plus słownik rozstrzygnięć i karta
    zgłoszenia. `input_text` to wątek zgłoszenia w formacie czytnika („ZGŁOSZENIE 33644\\nTemat:…").

    Słownik przychodzi w stanie, a nie z wnętrza grafu: wołający wybiera wersję, a karta zapisuje
    ją w `resolution_vocabulary_version` (zasada 7).
    """

    vocabulary: ResolutionVocabulary        # słownik rozstrzygnięć: dane klienta, do promptu parsującego
    output:     ParsedTicket | None = None  # karta zgłoszenia; ustawia węzeł `respond`
