import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent_graphs import gate_close, gate_reply
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.core_service.loader_dict_rules import get_rule_set
from app.entry_routers.gate.mapping import to_verdict_response
from app.entry_routers.gate.models import GateReplyRequest, VerdictResponse
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.models import TicketRequest
from app.entry_routers.streaming import STREAM_RESPONSES, GraphResponder, get_graph_responder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gates"])


@router.post("/gate/close", response_model=VerdictResponse, responses=STREAM_RESPONSES)
async def check_close(
    request:   TicketRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> VerdictResponse | StreamingResponse:
    """
    Description:
    Bramka zamknięcia — graf `gate_close`: czy z wątku wynika, co było problemem i co zrobiono.
    Werdykt opiniuje, blokadę egzekwuje helpdesk (zasada 11). Przy `Accept: text/event-stream`
    odpowiedzią jest strumień przebiegu, a werdykt przychodzi w nim na końcu.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie przychodzą przesyłki…", comments=[…])

    Example result:
        VerdictResponse(verdict="pass", reasons=[], …, overridable=True, rules_version=1)
    """
    rules = get_rule_set("gate_close")
    state = gate_close.STATE(input_text=to_raw_ticket(request).as_thread(), rules=rules.rules)

    def finish(
        final: gate_close.GateCloseState,  # np. GateCloseState(…, output=Verdict(…))
    ) -> VerdictResponse:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=GateCloseState(input_text="…", rules=["…"], output=Verdict(verdict="pass"))

        Example result:
            VerdictResponse(verdict="pass", …, overridable=True, rules_version=1)
        """
        logger.info("gate_close ticket_id=%s verdict=%s", request.ticket_id, final.output.verdict)

        return to_verdict_response(final, rules.version)

    return await responder.answer(build(gate_close), state, finish)


@router.post("/gate/reply", response_model=VerdictResponse, responses=STREAM_RESPONSES)
async def check_reply(
    request:   GateReplyRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> VerdictResponse | StreamingResponse:
    """
    Description:
    Bramka wysyłki — graf `gate_reply`: czy wiadomość do klienta nie łamie reguł wysyłki. Przy
    `Accept: text/event-stream` odpowiedzią jest strumień przebiegu, a werdykt przychodzi w nim
    na końcu.

    Example args:
        request=GateReplyRequest(ticket_id="41002", message="Proszę podać hasło do skrzynki.")

    Example result:
        VerdictResponse(verdict="block", reasons=["Prośba o hasło."], …, rules_version=1)
    """
    rules = get_rule_set("gate_reply")
    state = gate_reply.STATE(input_text=request.message, rules=rules.rules)

    def finish(
        final: gate_reply.GateReplyState,  # np. GateReplyState(…, output=Verdict(…))
    ) -> VerdictResponse:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=GateReplyState(input_text="…", rules=["…"], output=Verdict(verdict="block", …))

        Example result:
            VerdictResponse(verdict="block", …, overridable=True, rules_version=1)
        """
        logger.info("gate_reply ticket_id=%s verdict=%s", request.ticket_id, final.output.verdict)

        return to_verdict_response(final, rules.version)

    return await responder.answer(build(gate_reply), state, finish)
