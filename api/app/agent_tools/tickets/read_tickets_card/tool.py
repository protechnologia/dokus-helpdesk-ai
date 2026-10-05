"""
Description:
Prawdziwe narzędzie `read_tickets_card`: czyta z Qdranta karty zgłoszeń o podanych numerach.
Nie woła embeddera ani LLM-a — odczyt po numerze nie potrzebuje wektora.

    numery zgłoszeń → punkty kolekcji (po identyfikatorze) → karty z payloadu

Przed — zapytanie agenta:

    ReadTicketsCardQuery(ticket_ids=["90001", "90011"])

Po — wynik `search()` (zgłoszenie 90011 nie ma karty):

    ReadTicketsCardResult(
        cards        = [ParsedTicket(ticket_id="90001", …)],
        without_card = ["90011"],
    )

Co się dzieje po drodze:

1. Kolekcja zamienia numery na identyfikatory punktów i oddaje te, które ma, w kolejności
   żądania.
2. Payload każdego punktu staje się z powrotem `ParsedTicket`.
3. Numery, dla których punktu nie było, trafiają do `without_card`.

O czym pamiętać przy zmianach:

- Brak karty to nie błąd: do kolekcji trafiają tylko zgłoszenia, które przeszły filtr jakości.
- Payload niezgodny z `ParsedTicket` znaczy, że indeks zbudowano inną wersją kontraktu. Czekanie
  tego nie naprawi, stąd `DbQdrantConfigError`, a nie błąd „spróbuj później".
- Z punktem wracają wektory, których to narzędzie nie używa — taki jest odczyt kolekcji.
"""

import logging

from pydantic import ValidationError

from app.agent_tools.tickets.read_tickets_card.base import ReadTicketsCardToolBase
from app.agent_tools.tickets.read_tickets_card.models import (
    ReadTicketsCardQuery,
    ReadTicketsCardResult,
)
from app.core_model.tickets.parsed_ticket import ParsedTicket
from app.db_qdrant import DbQdrantConfigError, TicketPoint, TicketsCollection

logger = logging.getLogger(__name__)


def card_from_point(
    point: TicketPoint,  # np. TicketPoint(point_id="df3b…", payload={"ticket_id": "90001", …})
) -> ParsedTicket:
    """
    Description:
    Zamienia punkt z Qdranta na kartę: payload wraca do `ParsedTicket`, z którego został
    zapisany przy indeksacji.

    Example args:
        point=TicketPoint(point_id="df3b…", payload={"ticket_id": "90001", …}, …)

    Example result:
        ParsedTicket(ticket_id="90001", …)

    Raises:
        DbQdrantConfigError: payload nie spełnia kontraktu `ParsedTicket`
    """
    try:
        card = ParsedTicket.model_validate(point.payload)
    except ValidationError as exc:
        fields = sorted({
            ".".join(str(part) for part in error["loc"]) or "rekord"
            for error in exc.errors()
        })

        # `from None`: błąd Pydantica cytuje wartości pól, czyli treść zgłoszenia — nie do logów.
        raise DbQdrantConfigError(
            f"payload zgłoszenia {point.ticket_id!r} nie spełnia kontraktu ParsedTicket "
            f"(pola: {', '.join(fields)}) — indeks zbudowano inną wersją kontraktu, "
            f"przebuduj go: helpdesk tickets reindex"
        ) from None

    return card


class ReadTicketsCardTool(ReadTicketsCardToolBase):
    """
    Description:
    `read_tickets_card` na prawdziwym indeksie: kolekcja zgłoszeń oddaje punkty o podanych
    numerach, a ich payload wraca jako karty.

    Do czego:
    Źródło wiedzy agenta w grafach `search`, `suggest_questions` i `suggest_solution`: karty
    zgłoszeń znalezionych którymkolwiek wyszukiwaniem. Tylko do odczytu.

    Flow:
        1. `search()` czyta punkty po numerach zgłoszeń.
        2. Payload każdego punktu staje się kartą; numery bez punktu trafiają do `without_card`.
        3. `render_for_model()` i `cite()` z klasy bazowej robią z wyniku tekst i źródła.
    """

    def __init__(
        self,
        tickets: TicketsCollection,  # np. TicketsCollection(QdrantClient(…), "tickets", 768)
    ):
        """
        Description:
        Spina narzędzie z kolekcją zgłoszeń. Kolekcja jest wstrzykiwana, nie budowana tutaj
        (zasada 4).

        Example args:
            tickets=TicketsCollection(QdrantClient(base_url="http://qdrant:6333"), "tickets", 768)

        Example result:
            ReadTicketsCardTool gotowe do odczytu z kolekcji `tickets`
        """
        self._tickets = tickets

    async def search(
        self,
        query: ReadTicketsCardQuery,  # np. ReadTicketsCardQuery(ticket_ids=["90001", "90011"])
    ) -> ReadTicketsCardResult:
        """
        Description:
        Czyta karty zgłoszeń o podanych numerach, w kolejności żądania; numery bez karty wymienia
        osobno.

        Example args:
            query=ReadTicketsCardQuery(ticket_ids=["90001", "90011"])

        Example result:
            ReadTicketsCardResult(cards=[ParsedTicket(ticket_id="90001", …)],
                                  without_card=["90011"])

        Raises:
            DbQdrantError: Qdrant jest nieosiągalny albo odpowiedział błędem
            DbQdrantConfigError: payload punktu nie spełnia kontraktu `ParsedTicket`
        """
        # Bez powtórzeń, w kolejności żądania.
        wanted = list(dict.fromkeys(query.ticket_ids))

        points = await self._tickets.read_by_id(wanted)
        cards  = [card_from_point(point) for point in points]

        found        = {card.ticket_id for card in cards}
        without_card = [ticket_id for ticket_id in wanted if ticket_id not in found]

        # Same liczby: karty to dane klienta.
        logger.info(
            "read_tickets_card asked=%d cards=%d without_card=%d",
            len(wanted),
            len(cards),
            len(without_card),
        )

        result = ReadTicketsCardResult(
            cards        = cards,
            without_card = without_card,
        )

        return result

    async def aclose(self) -> None:
        """
        Description:
        Zamyka połączenie z Qdrantem. Sprzątający woła tylko to i nie musi wiedzieć, z czego
        narzędzie jest zbudowane.

        Example args:
            (brak)

        Example result:
            None
        """
        await self._tickets.aclose()
