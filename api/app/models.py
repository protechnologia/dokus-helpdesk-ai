from pydantic import BaseModel, Field


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
