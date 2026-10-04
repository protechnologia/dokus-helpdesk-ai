import logging

from fastapi import APIRouter, Depends, HTTPException

from app.agent_graphs import run_graph
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.agent_graphs.registry import variant_graphs
from app.entry_routers.mapping import (
    to_log_items,
    to_raw_ticket,
    to_source_items,
    to_usage_item,
)
from app.entry_routers.suggest.models import (
    SuggestRequest,
    SuggestResponse,
    VariantInfo,
    VariantsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["suggest"])


@router.get("/variants", response_model=VariantsResponse)
async def list_variants() -> VariantsResponse:
    """
    Description:
    Warianty odpowiedzi z rejestru grafów — helpdesk rysuje z tej listy guziki, zamiast trzymać
    własną, zaszytą.

    Example args:
        (brak)

    Example result:
        VariantsResponse(variants=[VariantInfo(name="handoff", label="Przekazanie sprawy", …), …])
    """
    variants = [
        VariantInfo(name=name, label=graph.LABEL, requires_hits=graph.REQUIRES_HITS)
        for name, graph in sorted(variant_graphs().items())
    ]

    return VariantsResponse(variants=variants)


@router.post("/suggest", response_model=SuggestResponse)
async def suggest_answer(
    request: SuggestRequest,
    build:   GraphBuilder = Depends(get_graph_builder),
) -> SuggestResponse:
    """
    Description:
    Propozycja odpowiedzi w wariancie, który wybrał człowiek — graf `suggest_<wariant>`. Wariant
    jest parametrem, nie trasą: nowy guzik to nowy katalog grafu bez zmiany tego pliku.

    Example args:
        request=SuggestRequest(ticket_id="41002", body="Nie przychodzą przesyłki…",
                               variant="questions")

    Example result:
        SuggestResponse(variant="questions", text="1. Od kiedy…", sources=[SourceItem(…), …])

    Raises:
        HTTPException: 422 przy nieznanym wariancie — literówka w nazwie guzika ma być widoczna
            od razu, a nie wygenerować coś innego, niż kliknął użytkownik
    """
    graphs = variant_graphs()

    if request.variant not in graphs:
        detail = f"nieznany wariant {request.variant!r}; dostępne: {', '.join(sorted(graphs))}"
        raise HTTPException(status_code=422, detail=detail)

    graph = graphs[request.variant]
    state = graph.STATE(input_text=to_raw_ticket(request).as_thread())
    final = await run_graph(build(graph), state)

    # Wariant bez narzędzi wiedzy nie ma pola `sources` — wraca z pustą listą, i to jest informacja.
    sources = getattr(final, "sources", [])

    response = SuggestResponse(
        variant = request.variant,
        text    = final.output.text,
        sources = to_source_items(sources),
        usage   = to_usage_item(final.usage),
        log     = to_log_items(final.log),
    )

    logger.info(
        "suggest ticket_id=%s variant=%s sources=%d",
        request.ticket_id,
        request.variant,
        len(response.sources),
    )

    return response
