import logging

from fastapi import APIRouter, Depends

from app.agent_graphs import polish, run_graph
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.routers.polish.models import PolishRequest, PolishResponse
from app.service.loader_dict_rules import get_rule_set

logger = logging.getLogger(__name__)

router = APIRouter(tags=["writing"])


@router.post("/polish", response_model=PolishResponse)
async def polish_text(
    request: PolishRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> PolishResponse:
    """
    Description:
    „Popraw" — graf `polish`: ten sam sens w poprawnej formie, według zasad stylu klienta. Wynik
    zawsze do akceptacji człowieka.

    Example args:
        request=PolishRequest(ticket_id="41002", text="przesylki juz ida, kolejka stala")

    Example result:
        PolishResponse(text="Dzień dobry, przesyłki z e-Doręczeń już docierają…")
    """
    rules = get_rule_set("polish")
    state = polish.STATE(input_text=request.text, rules=rules.rules)
    final = await run_graph(build(polish), state)

    logger.info("polish ticket_id=%s", request.ticket_id)

    return PolishResponse(text=final.output.text)
