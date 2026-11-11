import logging

from fastapi import APIRouter, Depends

from app.agent_graphs import gate_close, parse_ticket, run_graph
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.core_service.factory_closed_ticket_indexer import get_closed_ticket_indexer
from app.core_service.indexer_closed_ticket import ClosedTicketIndexer
from app.core_service.loader_dict_resolution import get_resolution_classes
from app.core_service.loader_dict_rules import get_rule_set
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.tickets.mapping import to_closed_ticket_response
from app.entry_routers.tickets.models import ClosedTicketResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tickets"])


@router.post("/tickets/closed", response_model=ClosedTicketResponse)
async def add_closed_ticket(
    request: TicketRequest,
    build:   GraphBuilder        = Depends(get_graph_builder),
    corpus:  ClosedTicketIndexer = Depends(get_closed_ticket_indexer),
) -> ClosedTicketResponse:
    """
    Description:
    Zamknięte zgłoszenie wraca do korpusu (p. 30): bramka zamknięcia ocenia wątek, a przy „pass”
    graf `parse_ticket` robi kartę, którą serwis korpusu zapisuje razem z surowym zgłoszeniem
    i wątkiem po anonimizacji i dokłada do indeksów albo z nich usuwa. Przy „block” korpus
    zostaje bez zmian. Tylko JSON, bez strumienia przebiegu: trasa uruchamia dwa grafy i zapis.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie przychodzą przesyłki…", comments=[…])

    Example result:
        ClosedTicketResponse(ticket_id="41002", outcome="indexed", replaced=False,
                             verdict="pass", …)

    Raises:
        LLMError, AnonymizationError: model albo anonimizator zawiódł — handler oddaje 503
        DbQdrantError, DbPostgresError, EmbeddingError: indeks nie przyjął zapisu po zapisaniu
            plików — handler oddaje 503, a pliki zostają w korpusie
    """
    raw    = to_raw_ticket(request)
    thread = raw.as_thread()
    rules  = get_rule_set("gate_close")

    # --- bramka: przy blokadzie korpus zostaje bez zmian ---
    checked = gate_close.STATE(input_text=thread, rules=rules.rules)
    gate    = await run_graph(build(gate_close), checked)

    if gate.output.verdict == "block":
        logger.info("closed_ticket ticket_id=%s verdict=block", request.ticket_id)

        blocked = to_closed_ticket_response(request.ticket_id, gate, rules.version)

        return blocked

    # --- karta: ten sam graf i ten sam wątek co karty korpusu ---
    state = parse_ticket.STATE(
        input_text = thread,
        ticket_id  = raw.ticket_id,
        date       = raw.date,
        vocabulary = get_resolution_classes(),
    )
    card = await run_graph(build(parse_ticket), state)

    # Do korpusu idzie wątek, z którego model zrobił kartę: anonimizacja w grafie bramki to
    # osobne wywołanie i przy modelu anonimizującym może wyjść inaczej.
    report = await corpus.add(raw, card.anonymized, card.output)

    logger.info(
        "closed_ticket ticket_id=%s verdict=pass indexed=%s replaced=%s",
        request.ticket_id,
        report.indexed,
        report.replaced,
    )

    response = to_closed_ticket_response(request.ticket_id, gate, rules.version, card, report)

    return response
