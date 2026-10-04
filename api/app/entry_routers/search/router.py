import logging

from fastapi import APIRouter, Depends

from app.agent_graphs import run_graph, search
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.engine_llm import ChatMessage
from app.entry_routers.mapping import (
    to_log_items,
    to_raw_ticket,
    to_source_items,
    to_usage_item,
)
from app.entry_routers.models import TicketRequest
from app.entry_routers.search.models import AgentQuery, SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])


def _agent_queries(
    messages: list[ChatMessage],  # np. [ChatMessage(role="assistant", tool_calls=[…]), …]
) -> list[AgentQuery]:
    """
    Description:
    Wyciąga z rozmowy zapytania, które agent wysłał do narzędzi wiedzy — bez wywołania odpowiedzi
    (`respond_search`), które niczego nie szuka.

    Example args:
        messages=[tool_call_turn("find_tickets_vector", {"problem": "…", "symptoms": "…"}), …]

    Example result:
        [AgentQuery(tool="find_tickets_vector", arguments={"problem": "…", "symptoms": "…"})]
    """
    queries = [
        AgentQuery(tool=call.name, arguments=call.arguments)
        for message in messages
        for call in message.tool_calls
        if call.name in search.TOOL_NAMES
    ]

    return queries


@router.post("/search", response_model=SearchResponse)
async def search_tickets(
    request: TicketRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> SearchResponse:
    """
    Description:
    Podobne zgłoszenia i fragmenty instrukcji do zgłoszenia — graf `search`. Cienki adapter:
    żądanie na stan, graf, stan na odpowiedź. Brak źródeł to 200 z pustą listą, nie 404.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        SearchResponse(sources=[SourceItem(…), …],
                       queries=[AgentQuery(tool="find_tickets_vector", …)])
    """
    state = search.STATE(input_text=to_raw_ticket(request).as_thread())
    final = await run_graph(build(search), state)

    response = SearchResponse(
        sources = to_source_items(final.sources),
        queries = _agent_queries(final.messages),
        usage   = to_usage_item(final.usage),
        log     = to_log_items(final.log),
    )

    # Same identyfikatory i liczby — źródła niosą dane klientów (CLAUDE.md -> „Logi").
    logger.info(
        "search ticket_id=%s sources=%d queries=%d",
        request.ticket_id,
        len(response.sources),
        len(response.queries),
    )

    return response
