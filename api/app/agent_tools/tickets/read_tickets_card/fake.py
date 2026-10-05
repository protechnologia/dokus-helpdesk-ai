from collections.abc import Sequence

from app.agent_tools.tickets.fake_tickets import default_cards
from app.agent_tools.tickets.read_tickets_card.base import ReadTicketsCardToolBase
from app.agent_tools.tickets.read_tickets_card.models import (
    ReadTicketsCardQuery,
    ReadTicketsCardResult,
)
from app.core_model.dicts.resolution_vocabulary import ResolutionVocabulary
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.core_service.loader_dict_resolution import get_resolution_classes


class FakeReadTicketsCardTool(ReadTicketsCardToolBase):
    """
    Description:
    Atrapa `read_tickets_card`: zamiast Qdranta oddaje karty ze zmyślonego zestawu wspólnego dla
    wszystkich atrap narzędzi zgłoszeń (`agent_tools/tickets/fake_tickets.py`). Odpowiada NA TO,
    o co pytano, jak atrapa `read_docs`.

    Flow:
        1. Test tworzy ją z własnymi kartami albo z zestawem wbudowanym.
        2. Każde `search()` zapisuje zapytanie w `queries` i oddaje karty żądanych numerów
           w kolejności żądania; numer bez karty trafia do `without_card`.
        3. `render_for_model()` i `cite()` pochodzą z klasy wspólnej z prawdziwym narzędziem.
    """

    def __init__(
        self,
        cards:      Sequence[ParsedTicket] | None = None,  # np. [ParsedTicket(ticket_id="90001")]
        resolution: ResolutionVocabulary | None = None,    # np. ResolutionVocabulary(version=1, …)
    ):
        """
        Description:
        Ustala karty, z których atrapa czyta, i słownik, z którego powstaje lista klas w opisie
        narzędzia; zakłada dziennik zapytań. Bez podanego słownika bierze zestaw domyślny —
        ten, na którym napisano wbudowane karty.

        Example args:
            cards=None
            resolution=None

        Example result:
            FakeReadTicketsCardTool czytająca wbudowane cztery karty
        """
        super().__init__(resolution if resolution is not None else get_resolution_classes())

        cards = list(cards) if cards is not None else default_cards()

        self._cards = {card.ticket_id: card for card in cards}

        # Publiczne celowo: testy sprawdzają, które karty agent przeczytał.
        self.queries: list[ReadTicketsCardQuery] = []

    async def search(
        self,
        query: ReadTicketsCardQuery,  # np. ReadTicketsCardQuery(ticket_ids=["90001", "90011"])
    ) -> ReadTicketsCardResult:
        """
        Description:
        Zapisuje zapytanie i oddaje karty żądanych numerów; numery bez karty wymienia osobno.

        Example args:
            query=ReadTicketsCardQuery(ticket_ids=["90001", "90011"])

        Example result:
            ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="90001", …)],
                                  without_card=["90011"])
        """
        self.queries.append(query)

        # Bez powtórzeń, w kolejności żądania — jak prawdziwy odczyt.
        wanted = list(dict.fromkeys(query.ticket_ids))

        with_card = [ticket_id for ticket_id in wanted if ticket_id in self._cards]

        result = ReadTicketsCardResult(
            cards        = [self._cards[ticket_id] for ticket_id in with_card],
            without_card = [ticket_id for ticket_id in wanted if ticket_id not in self._cards],
        )

        return result
