import logging

from fastapi import APIRouter, Depends

from app.graph import parse_ticket, run_graph
from app.graph.factory import GraphBuilder, get_graph_builder
from app.routers.mapping import to_raw_ticket
from app.routers.models import TicketRequest
from app.routers.parse_ticket.models import TicketCard
from app.service.loader_dict_resolution import get_resolution_classes

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
    final = await run_graph(build(parse_ticket), state)
    card  = final.output

    response = TicketCard(
        ticket_id         = card.ticket_id,
        date              = card.date,
        component         = card.component,
        problem           = card.problem,
        symptoms          = card.symptoms,
        error_codes       = card.error_codes,
        cause             = card.cause,
        solution          = card.solution,
        resolution        = card.resolution,
        questions_summary = card.questions_summary,
    )

    logger.info("parse_ticket ticket_id=%s", request.ticket_id)

    return response
