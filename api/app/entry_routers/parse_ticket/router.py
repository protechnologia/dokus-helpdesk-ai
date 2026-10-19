import logging

from fastapi import APIRouter, Depends

from app.agent_graphs import parse_ticket, run_graph
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.parse_ticket.mapping import to_ticket_card
from app.entry_routers.parse_ticket.models import TicketCard

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tickets"])


@router.post("/parse-ticket", response_model=TicketCard)
async def read_ticket_card(
    request: TicketRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> TicketCard:
    """
    Description:
    Karta zgłoszenia — graf `parse_ticket`: wątek sparsowany promptem korpusu, ze słownikiem
    rozstrzygnięć w bieżącej wersji.

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
    final    = await run_graph(build(parse_ticket), state)
    response = to_ticket_card(final)

    logger.info("parse_ticket ticket_id=%s", request.ticket_id)

    return response
