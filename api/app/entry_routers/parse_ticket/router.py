import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent_graphs import parse_ticket
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.parse_ticket.mapping import to_ticket_card
from app.entry_routers.parse_ticket.models import TicketCard
from app.entry_routers.streaming import STREAM_RESPONSES, GraphResponder, get_graph_responder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tickets"])


@router.post("/parse-ticket", response_model=TicketCard, responses=STREAM_RESPONSES)
async def read_ticket_card(
    request:   TicketRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> TicketCard | StreamingResponse:
    """
    Description:
    Karta zgłoszenia — graf `parse_ticket`: wątek sparsowany promptem korpusu, ze słownikiem
    rozstrzygnięć w bieżącej wersji. Przy `Accept: text/event-stream` odpowiedzią jest strumień
    przebiegu, a karta przychodzi w nim na końcu.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        TicketCard(ticket_id="41002", component="ePUAP", problem="Wysyłka kończy się błędem", …)
    """
    raw   = to_raw_ticket(request)
    state = parse_ticket.STATE(
        input_text = raw.as_thread(),
        ticket_id  = raw.ticket_id,
        date       = raw.date,
        vocabulary = get_resolution_classes(),
    )

    def finish(
        final: parse_ticket.ParseTicketState,  # np. ParseTicketState(…, output=ParsedTicket(…))
    ) -> TicketCard:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=ParseTicketState(input_text="…", ticket_id="41002", …, output=ParsedTicket(…))

        Example result:
            TicketCard(ticket_id="41002", component="ePUAP", …)
        """
        response = to_ticket_card(final)

        logger.info("parse_ticket ticket_id=%s", request.ticket_id)

        return response

    return await responder.answer(build(parse_ticket), state, finish)
