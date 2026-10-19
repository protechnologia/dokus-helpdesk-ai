import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.agent_graphs import GraphState
from app.agent_graphs.factory import GraphBuilder, get_graph_builder
from app.agent_graphs.registry import variant_graphs
from app.entry_routers.mapping import to_raw_ticket
from app.entry_routers.streaming import STREAM_RESPONSES, GraphResponder, get_graph_responder
from app.entry_routers.suggest.mapping import to_suggest_response
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


@router.post("/suggest", response_model=SuggestResponse, responses=STREAM_RESPONSES)
async def suggest_answer(
    request:   SuggestRequest,
    build:     GraphBuilder   = Depends(get_graph_builder),
    responder: GraphResponder = Depends(get_graph_responder),
) -> SuggestResponse | StreamingResponse:
    """
    Description:
    Propozycja odpowiedzi w wariancie, który wybrał człowiek — graf `suggest_<wariant>`. Wariant
    jest parametrem, nie trasą: nowy guzik to nowy katalog grafu bez zmiany tego pliku. Przy
    `Accept: text/event-stream` odpowiedzią jest strumień przebiegu, a propozycja przychodzi
    w nim na końcu; nieznany wariant to 422 także wtedy, bo pada przed startem strumienia.

    Example args:
        request=SuggestRequest(ticket_id="41002", body="Nie przychodzą przesyłki…",
                               variant="questions")

    Wariant, który wymaga źródeł, bez odczytanych źródeł wraca bez treści dla klienta: `text` jest
    puste, lista źródeł pusta, a uwagi dla wdrożeniowca zostają. Tak samo, z `text` pustym
    i uwagami, wraca wariant z pytaniami, gdy pytań już nie trzeba; źródła wtedy zostają.

    Example result:
        SuggestResponse(variant="questions", text="1. Od kiedy…",
                        internal_notes="1: odcina zacięcie kolejki…", sources=[SourceItem(…), …])

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

    def finish(
        final: GraphState,  # np. SuggestQuestionsState(…, sources=[…], output=Proposal(…))
    ) -> SuggestResponse:
        """
        Description:
        Odpowiedź trasy ze stanu końcowego i wpis w logu usługi — wspólne dla JSON-a
        i strumienia.

        Example args:
            final=SuggestQuestionsState(input_text="…", sources=[…], output=Proposal(…))

        Example result:
            SuggestResponse(variant="questions", text="1. Od kiedy…", internal_notes="1: …")
        """
        response = to_suggest_response(final, request.variant)

        logger.info(
            "suggest ticket_id=%s variant=%s sources=%d proposal=%s notes=%s",
            request.ticket_id,
            request.variant,
            len(response.sources),
            response.text is not None,
            bool(response.internal_notes),
        )

        return response

    return await responder.answer(build(graph), state, finish)
