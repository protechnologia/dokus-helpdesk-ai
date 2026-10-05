import json
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

# Pole wyniku wyszukiwania po znaczeniu: ile trafień odciął próg podobieństwa.
DROPPED_FIELD = "dropped_below_threshold"


def _dropped_below_threshold(
    result_text: str | None,  # np. '{"tickets": [], "dropped_below_threshold": 3}'
) -> int | None:
    """
    Description:
    Czyta z wyniku narzędzia, ile trafień odciął próg podobieństwa. Wynik narzędzia to JSON
    z polami pod nazwami ze schematu, więc licznik jest w nim wprost. Brak wyniku, błąd zamiast
    wyniku albo narzędzie bez progu dają `None`.

    Example args:
        result_text='{"tickets": [], "dropped_below_threshold": 3}'

    Example result:
        3
    """
    # --- wywołanie bez odpowiedzi: tura ucięta limitem tur ---
    if result_text is None:
        return None

    try:
        body = json.loads(result_text)
    except json.JSONDecodeError:  # nie JSON, więc nie wynik narzędzia
        return None

    dropped = body.get(DROPPED_FIELD) if isinstance(body, dict) else None

    return dropped if isinstance(dropped, int) else None


def _agent_queries(
    messages: list[ChatMessage],  # np. [ChatMessage(role="assistant", tool_calls=[…]), …]
) -> list[AgentQuery]:
    """
    Description:
    Wyciąga z rozmowy zapytania, które agent wysłał do narzędzi wiedzy — bez wywołania odpowiedzi
    (`respond_search`), które niczego nie szuka. Do wyszukiwania po znaczeniu dokłada licznik
    trafień odciętych progiem, odczytany z wyniku tego wywołania.

    Example args:
        messages=[tool_call_turn("find_tickets_vector", {"problem": "…", "symptoms": "…"}),
                  ChatMessage(role="tool", call_id="call_1", content='{"tickets": […], …}')]

    Example result:
        [AgentQuery(tool="find_tickets_vector", arguments={"problem": "…", "symptoms": "…"},
                    dropped_below_threshold=3)]
    """
    # Wynik wywołania to wiadomość `tool` z jego `call_id`.
    results = {message.call_id: message.content for message in messages if message.role == "tool"}

    queries = [
        AgentQuery(
            tool                    = call.name,
            arguments               = call.arguments,
            dropped_below_threshold = _dropped_below_threshold(results.get(call.call_id)),
        )
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
                       queries=[AgentQuery(tool="find_tickets_vector", …,
                                           dropped_below_threshold=0), …])
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
        "search ticket_id=%s sources=%d queries=%d dropped_below_threshold=%d",
        request.ticket_id,
        len(response.sources),
        len(response.queries),
        sum(query.dropped_below_threshold or 0 for query in response.queries),
    )

    return response
