import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent_graphs import search
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.search.mapping import to_search_response
from app.entry_routers.search.models import SearchResponse
from app.entry_routers.streaming import STREAM_RESPONSES, GraphResponder, get_graph_responder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


@router.post("/search", response_model=SearchResponse, responses=STREAM_RESPONSES)
async def search_tickets(
    request:   TicketRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> SearchResponse | StreamingResponse:
    """
    Description:
    Rozpoznanie do zgłoszenia w zgłoszeniach, instrukcjach i kodzie aplikacji — graf `search`.
    Cienki adapter: żądanie na stan, graf, stan na odpowiedź. Brak źródeł to 200 z pustą listą,
    nie 404; uwagi dla wdrożeniowca wracają także wtedy. Przy `Accept: text/event-stream`
    odpowiedzią jest strumień przebiegu, a ta sama odpowiedź przychodzi w nim na końcu.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        SearchResponse(sources=[SourceItem(…), …],
                       internal_notes="## Zgłoszenia historyczne\n- 41002 (2026-03-14): …",
                       queries=[AgentQuery(tool="find_tickets_vector", …,
                                           dropped_below_threshold=0), …])
    """
    state = search.STATE(input_text=to_raw_ticket(request).as_thread())

    def finish(
        final: search.SearchState,  # np. SearchState(…, sources=[…], output=SearchNotes(…))
    ) -> SearchResponse:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=SearchState(input_text="…", sources=[SourceRef(…)], output=SearchNotes(…))

        Example result:
            SearchResponse(sources=[SourceItem(…)], internal_notes="…", queries=[…])
        """
        response = to_search_response(final)

        # Same identyfikatory i liczby — źródła i uwagi niosą dane klientów (CLAUDE.md ->
        # „Logi"), więc z uwag idzie do logu tylko długość.
        logger.info(
            "search ticket_id=%s sources=%d queries=%d dropped_below_threshold=%d notes_chars=%d",
            request.ticket_id,
            len(response.sources),
            len(response.queries),
            sum(query.dropped_below_threshold or 0 for query in response.queries),
            len(response.internal_notes),
        )

        return response

    return await responder.answer(build(search), state, finish)
