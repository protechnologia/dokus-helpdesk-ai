from typing import Literal

from pydantic import BaseModel, Field

# The three modes PolDense distinguishes by an input prefix (`[query]: `, none, `[sts]: `).
# The stub validates the value and ignores it; stage 2 turns it into the actual prefix. Modes
# must never be mixed inside one vector space — hence a closed set, not a free string.
EmbeddingMode = Literal["query", "passage", "sts"]


class HealthResponse(BaseModel):
    """
    Description:
    Payload of `GET /health`. Says nothing about configuration — a liveness probe is reachable
    to anyone who can reach the service, so it must not leak model names or dimensions.
    """

    status: str = Field(examples=["ok"])


class ErrorResponse(BaseModel):
    """
    Description:
    Uniform error payload for every handled failure, in the same shape `api` uses — the caller of
    this service is that API, and one shape means one parsing path on the other side.
    `request_id` lets both services quote the same value when the failure is investigated.
    """

    detail:     str        = Field(examples=["Encoding failed"])
    request_id: str | None = Field(default=None, examples=["6f1c…"])


class EmbedRequest(BaseModel):
    """
    Description:
    Input of `POST /embed`. A batch of texts embedded in ONE mode: a caller mixing modes in a
    single call would be about to mix them in a single vector space too.
    """

    texts: list[str] = Field(min_length=1, examples=[["Drukarka nie drukuje po aktualizacji"]])
    # No default on purpose: the mode is the easiest thing in this project to get silently wrong,
    # so the caller has to state it rather than inherit whatever we would have picked.
    mode:  EmbeddingMode = Field(examples=["passage"])


class EmbedResponse(BaseModel):
    """
    Description:
    Output of `POST /embed` — vectors in the order of the submitted texts, plus the identity of
    what produced them. `model` and `dimension` are part of the answer because a collection is
    bound to both: changing either means a new Qdrant collection, never a migration.
    """

    vectors:   list[list[float]] = Field(examples=[[[0.01, -0.04]]])
    model:     str               = Field(examples=["stub-deterministic"])
    dimension: int               = Field(examples=[768])
