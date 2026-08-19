from datetime import date as Date

from pydantic import BaseModel, Field


class SearchComment(BaseModel):
    """
    Description:
    One comment of the thread being searched with, as the caller sends it.

    Only `body` is required. `role` and `created_at` are labelled in the prompt but deliberately
    not acted upon — this database has documented cases of both being wrong (the author is
    inverted in the "Automat mailowy" category), so the model is told to weigh content over
    labels. Sending them helps; missing them costs little.
    """

    body:       str = Field(examples=["Proszę sprawdzić uprawnienia certyfikatu."])
    role:       str = Field(default="", examples=["konsultant", "klient"])
    created_at: str = Field(default="", examples=["2026-06-23 12:01:21"])


class SearchRequest(BaseModel):
    """
    Description:
    Payload of `POST /search`: one incoming ticket, in the shape the helpdesk already holds it.

    Do czego:
    An API model kept separate from the domain `RawTicket` on purpose — the wire contract must not
    move every time the domain model does, and the domain must not leak internal fields outward
    (CLAUDE.md -> "Warstwy kodu").

    Which fields are required, and why only these two: `ticket_id` is the thread that ties a
    proposal back to the ticket in logs and in later feedback, and `body` IS the query. The rest
    describe the ticket without steering the search, so demanding them would raise the cost of
    integration without improving an answer. A ticket in progress already has an id and a date —
    both are assigned when it is opened.
    """

    ticket_id: str  = Field(examples=["41002"])
    body:      str  = Field(examples=["Nie mogę wysłać pisma przez ePUAP, błąd komunikacji."])
    # Defaults to today: a ticket being searched with is by definition current, and the date does
    # not reach the vector — it matters for records IN the index (staleness, seasonality), not for
    # the question asked of it.
    date:      Date | None = Field(default=None, examples=["2026-08-19"])
    subject:   str  = Field(default="", examples=["Błąd wysyłki"])
    # Optional because its only meaningful value is "Automat mailowy", which marks threads whose
    # quoted mail history needs cleaning. Another helpdesk may not have this field at all.
    category:  str  = Field(default="", examples=["Automat mailowy", "Błąd"])
    comments:  list[SearchComment] = Field(default_factory=list)


class SearchQuery(BaseModel):
    """
    Description:
    What the parser made of the incoming thread — the whole reading, not just the embedded part.

    Do czego:
    Debugging surface. A surprising hit list is explained by an unexpected reading of the ticket
    far more often than by the search itself, and only `problem` + `symptoms` reach the vector —
    so showing just those two would hide a misread `component` or a dropped error code until it
    resurfaced as a strange proposal in stage 6.

    A model of its own rather than `ParsedTicket` passed through: the domain model must not go out
    over HTTP (CLAUDE.md -> "Warstwy kodu"), and the two contracts have to be free to move apart.

    Carries the customer's text (names may appear in `problem` or `symptoms`), which is acceptable
    here because the caller is the helpdesk that owns the original ticket — but it is a reason to
    keep this endpoint behind authentication once there is any (CLAUDE.md -> TODO).
    """

    component:         str       = Field(default="", examples=["ePUAP"])
    problem:           str       = Field(default="", examples=["Wysyłka kończy się błędem"])
    symptoms:          str       = Field(default="", examples=["Komunikat o braku sieci"])
    error_codes:       list[str] = Field(default_factory=list, examples=[["ERR-4210"]])
    cause:             str       = Field(default="", examples=["brak"])
    solution:          str       = Field(default="", examples=["brak"])
    resolution:        str       = Field(default="", examples=["naprawione"])
    questions_summary: str       = Field(default="", examples=["brak"])


class SearchHit(BaseModel):
    """
    Description:
    One historical ticket found for the query: how well it matched, and the fields an answer is
    built from.

    Fields are listed explicitly rather than passing the Qdrant payload through. The payload is a
    storage detail, and forwarding it whole would publish whatever we happen to store — the exact
    leak the API/domain split exists to prevent.
    """

    ticket_id:         str   = Field(examples=["33644"])
    score:             float = Field(examples=[0.87])
    # Unconditional, because staleness, contradictions between records and seasonality all depend
    # on it (CLAUDE.md -> "Twarde reguły promptu generacji").
    date:              str   = Field(default="", examples=["2026-03-14"])
    component:         str   = Field(default="", examples=["ePUAP"])
    problem:           str   = Field(default="", examples=["Wysyłka kończy się błędem"])
    symptoms:          str   = Field(default="", examples=["Komunikat o braku sieci"])
    cause:             str   = Field(default="", examples=["Certyfikat bez uprawnienia"])
    solution:          str   = Field(default="", examples=["Wygenerowano nowy certyfikat."])
    resolution:        str   = Field(default="", examples=["naprawione"])
    questions_summary: str   = Field(default="", examples=["pytano o wersję przeglądarki"])


class SearchResponse(BaseModel):
    """
    Description:
    Payload of `POST /search`: the hits, what the model understood the ticket to be, and how many
    records the threshold removed.

    `dropped_below_threshold` answers the one question a caller has about a short list — "was
    there nothing, or did the threshold cut it?" — which no count of hits can answer on its own.
    """

    hits:                    list[SearchHit] = Field(default_factory=list)
    query:                   SearchQuery     = Field(default_factory=SearchQuery)
    dropped_below_threshold: int             = Field(default=0, examples=[3])


class HealthResponse(BaseModel):
    """
    Description:
    Payload of `GET /health`. Deliberately says nothing about configuration — a liveness probe
    is reachable to anyone who can reach the service, so it must not leak provider names,
    endpoints or model identifiers.
    """

    status: str = Field(examples=["ok"])


class ErrorResponse(BaseModel):
    """
    Description:
    Uniform error payload for every handled failure, so clients parse one shape instead of
    three. `request_id` lets a caller quote a single value that stitches together all log
    entries of the failed request.
    """

    detail:     str         = Field(examples=["Ticket not found"])
    request_id: str | None  = Field(default=None, examples=["6f1c…"])
