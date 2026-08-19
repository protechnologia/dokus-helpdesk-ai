import logging
from datetime import date as Date

from fastapi import APIRouter, Depends, HTTPException

from app.factory import get_searcher
from app.model.rag_search_result import SearchResult
from app.model.ticket_raw import RawTicket
from app.model.ticket_raw_comment import RawComment
from app.models import SearchHit, SearchQuery, SearchRequest, SearchResponse
from app.service.rag_searcher import RagSearcher, SearchParseError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["rag"])

# What a comment carries when the caller did not label it. The parsing prompt is told to weigh
# content over labels — this corpus has documented cases of the author being inverted — so an
# unlabelled comment is a thinner input, never an invalid one.
UNKNOWN_ROLE = "nieznany"

# Placed in the thread where the source would have a timestamp. Comments keep the order they
# arrived in, which is the part that carries meaning; the clock reading is context, not sequence.
UNKNOWN_TIME = ""


def _to_raw_ticket(
    request: SearchRequest,  # e.g. SearchRequest(ticket_id="41002", body="Nie działa wysyłka…")
) -> RawTicket:
    """
    Description:
    Maps the wire model onto the domain one, so the searcher receives exactly the shape the corpus
    was parsed from.

    Written out by hand rather than by copying fields wholesale: the two models are allowed to
    drift apart, and an automatic mapping would silently forward whatever the API happens to
    accept (CLAUDE.md -> "Warstwy kodu", separate API and domain models).

    Example args:
        request=SearchRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        RawTicket(ticket_id="41002", date=date(2026, 8, 19), body="Nie mogę wysłać pisma…")
    """
    return RawTicket(
        ticket_id = request.ticket_id,
        # A ticket being searched with is current by definition, so "unspecified" means "today".
        date      = request.date or Date.today(),
        category  = request.category,
        subject   = request.subject,
        body      = request.body,
        comments  = [
            RawComment(
                # `kind` describes a workflow state of the SOURCE database and has no meaning for
                # an incoming thread, so it is not part of the API contract at all.
                kind       = "zwyczajny",
                role       = comment.role or UNKNOWN_ROLE,
                created_at = comment.created_at or UNKNOWN_TIME,
                body       = comment.body,
            )
            for comment in request.comments
        ],
    )


def _to_response(
    result: SearchResult,  # e.g. SearchResult(query=ParsedTicket(…), hits=[TicketHit(…)])
) -> SearchResponse:
    """
    Description:
    Maps the domain result onto the wire model, naming every field that goes out.

    Hit fields are read off the payload with defaults rather than indexed: a record written by an
    older schema must produce a thinner answer, not a 500 in the middle of a search.

    Example args:
        result=SearchResult(query=ParsedTicket(…), hits=[TicketHit(score=0.87, …)])

    Example result:
        SearchResponse(hits=[SearchHit(ticket_id="33644", score=0.87, …)], …)
    """
    parsed = result.query

    return SearchResponse(
        hits = [
            SearchHit(
                ticket_id         = hit.ticket_id,
                score             = hit.score,
                date              = hit.payload.get("date", ""),
                component         = hit.payload.get("component", ""),
                problem           = hit.payload.get("problem", ""),
                symptoms          = hit.payload.get("symptoms", ""),
                cause             = hit.payload.get("cause", ""),
                solution          = hit.payload.get("solution", ""),
                resolution        = hit.payload.get("resolution", ""),
                questions_summary = hit.payload.get("questions_summary", ""),
            )
            for hit in result.hits
        ],
        # The whole reading, not just the embedded half: a misread `component` or a dropped error
        # code is invisible in `problem` alone and would only surface as a strange proposal later.
        query = SearchQuery(
            component         = parsed.component,
            problem           = parsed.problem,
            symptoms          = parsed.symptoms,
            error_codes       = parsed.error_codes,
            cause             = parsed.cause,
            solution          = parsed.solution,
            resolution        = parsed.resolution,
            questions_summary = parsed.questions_summary,
        ),
        dropped_below_threshold = result.dropped_below_threshold,
    )


@router.post("/search", response_model=SearchResponse)
async def search_tickets(
    request:  SearchRequest,
    searcher: RagSearcher = Depends(get_searcher),
) -> SearchResponse:
    """
    Description:
    Finds historical tickets resembling an incoming one. A thin adapter: it maps the wire model in,
    calls one service method, and maps the result out — no retrieval logic lives here.

    Finding nothing is a 200 with an empty list, not a 404. "New kind of problem" is a correct and
    frequent answer in this corpus (47% of records are singletons), and a 404 would tell the
    caller that the request was wrong.

    Example args:
        request=SearchRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        SearchResponse(hits=[SearchHit(ticket_id="33644", score=0.87, …)], …)

    Raises:
        HTTPException: 422 when the thread could not be parsed into a ticket — that is a statement
            about the INPUT, unlike a 503 from an unreachable dependency
    """
    raw = _to_raw_ticket(request)

    try:
        result = await searcher.search(raw)
    except SearchParseError as exc:
        # The reasons name the offending fields and come from our own validator, so they are safe
        # to return — unlike a provider's exception text, which may quote the prompt.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Identifiers and counts only: hit payloads carry customer data (CLAUDE.md -> "Logi").
    logger.info(
        "search ticket_id=%s hits=%d",
        request.ticket_id,
        len(result.hits),
    )

    return _to_response(result)
