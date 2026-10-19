import logging

from fastapi import APIRouter, Depends

from app.agent_graphs import run_graph, search
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.search.mapping import to_search_response
from app.entry_routers.search.models import SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


@router.post("/search", response_model=SearchResponse)
async def search_tickets(
    request: TicketRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> SearchResponse:
    """
    Description:
    Rozpoznanie do zgłoszenia w zgłoszeniach, instrukcjach i kodzie aplikacji — graf `search`.
    Cienki adapter: żądanie na stan, graf, stan na odpowiedź. Brak źródeł to 200 z pustą listą,
    nie 404; uwagi dla wdrożeniowca wracają także wtedy.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        SearchResponse(sources=[SourceItem(…), …],
                       internal_notes="## Zgłoszenia historyczne\n- 41002 (2026-03-14): …",
                       queries=[AgentQuery(tool="find_tickets_vector", …,
                                           dropped_below_threshold=0), …])
    """
    state    = search.STATE(input_text=to_raw_ticket(request).as_thread())
    final    = await run_graph(build(search), state)
    response = to_search_response(final)

    # Same identyfikatory i liczby — źródła i uwagi niosą dane klientów (CLAUDE.md -> „Logi"),
    # więc z uwag idzie do logu tylko długość.
    logger.info(
        "search ticket_id=%s sources=%d queries=%d dropped_below_threshold=%d notes_chars=%d",
        request.ticket_id,
        len(response.sources),
        len(response.queries),
        sum(query.dropped_below_threshold or 0 for query in response.queries),
        len(response.internal_notes),
    )

    return response
