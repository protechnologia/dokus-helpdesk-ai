import logging

from fastapi import APIRouter, Depends

from app.factory import GraphBuilder, get_graph_builder
from app.graph import gate_close, gate_reply, run_graph
from app.model.gate_verdict import Verdict
from app.models import GateReplyRequest, TicketRequest, VerdictResponse
from app.routers.mapping import to_raw_ticket
from app.service.loader_dict_rules import get_rule_set

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gates"])


def _to_response(
    verdict:       Verdict,  # np. Verdict(verdict="block", reasons=["…"], hint="…")
    rules_version: int,      # np. 1
) -> VerdictResponse:
    """
    Description:
    Zamienia werdykt grafu na odpowiedź bramki — z furtką i wersją zestawu reguł.

    Example args:
        verdict=Verdict(verdict="block", reasons=["Nie widać, co zrobiono."], hint="Dopisz…")
        rules_version=1

    Example result:
        VerdictResponse(verdict="block", …, overridable=True, rules_version=1)
    """
    response = VerdictResponse(
        verdict       = verdict.verdict,
        reasons       = verdict.reasons,
        missing       = verdict.missing,
        hint          = verdict.hint,
        rules_version = rules_version,
    )

    return response


@router.post("/gate/close", response_model=VerdictResponse)
async def check_close(
    request: TicketRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> VerdictResponse:
    """
    Description:
    Bramka zamknięcia — graf `gate_close`: czy z wątku wynika, co było problemem i co zrobiono.
    Werdykt opiniuje, blokadę egzekwuje helpdesk (zasada 11).

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie przychodzą przesyłki…", comments=[…])

    Example result:
        VerdictResponse(verdict="pass", reasons=[], …, overridable=True, rules_version=1)
    """
    rules = get_rule_set("gate_close")
    state = gate_close.STATE(input_text=to_raw_ticket(request).as_thread(), rules=rules.rules)
    final = await run_graph(build(gate_close), state)

    logger.info("gate_close ticket_id=%s verdict=%s", request.ticket_id, final.output.verdict)

    return _to_response(final.output, rules.version)


@router.post("/gate/reply", response_model=VerdictResponse)
async def check_reply(
    request: GateReplyRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> VerdictResponse:
    """
    Description:
    Bramka wysyłki — graf `gate_reply`: czy wiadomość do klienta nie łamie reguł wysyłki.

    Example args:
        request=GateReplyRequest(ticket_id="41002", message="Proszę podać hasło do skrzynki.")

    Example result:
        VerdictResponse(verdict="block", reasons=["Prośba o hasło."], …, rules_version=1)
    """
    rules = get_rule_set("gate_reply")
    state = gate_reply.STATE(input_text=request.message, rules=rules.rules)
    final = await run_graph(build(gate_reply), state)

    logger.info("gate_reply ticket_id=%s verdict=%s", request.ticket_id, final.output.verdict)

    return _to_response(final.output, rules.version)
