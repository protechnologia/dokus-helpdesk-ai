import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent_graphs import polish
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.core_service.loader_dict_rules import get_rule_set
from app.entry_routers.polish.mapping import to_polish_response
from app.entry_routers.polish.models import PolishRequest, PolishResponse
from app.entry_routers.streaming import STREAM_RESPONSES, GraphResponder, get_graph_responder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["writing"])


@router.post("/polish", response_model=PolishResponse, responses=STREAM_RESPONSES)
async def polish_text(
    request:   PolishRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> PolishResponse | StreamingResponse:
    """
    Description:
    „Popraw" — graf `polish`: ten sam sens w poprawnej formie, według zasad stylu klienta. Wynik
    zawsze do akceptacji człowieka. Przy `Accept: text/event-stream` odpowiedzią jest strumień
    przebiegu, a poprawiony tekst przychodzi w nim na końcu.

    Example args:
        request=PolishRequest(ticket_id="41002", text="przesylki juz ida, kolejka stala")

    Example result:
        PolishResponse(text="Dzień dobry, przesyłki z e-Doręczeń już docierają…")
    """
    rules = get_rule_set("polish")
    state = polish.STATE(input_text=request.text, rules=rules.rules)

    def finish(
        final: polish.PolishState,  # np. PolishState(…, output=PolishedText(text="Dzień dobry…"))
    ) -> PolishResponse:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=PolishState(input_text="…", rules=["…"], output=PolishedText(text="…"))

        Example result:
            PolishResponse(text="Dzień dobry, przesyłki z e-Doręczeń już docierają…")
        """
        logger.info("polish ticket_id=%s", request.ticket_id)

        return to_polish_response(final)

    return await responder.answer(build(polish), state, finish)
