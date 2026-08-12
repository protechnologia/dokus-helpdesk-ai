from pydantic import BaseModel, Field

from app.model.ticket_parsed import ParsedTicket


class ParseResult(BaseModel):
    """
    Description:
    Outcome of parsing ONE ticket: the artifact when it worked, the reason when it did not, and
    the accounting either way. Failure is a value here rather than an exception because a run over
    a corpus must report what it could not parse and keep going — and because a call that failed
    validation still cost money, so its usage belongs in the total.
    """

    ticket_id: str                 = Field(examples=["33644"])
    ticket:    ParsedTicket | None = Field(default=None)
    errors:    list[str]           = Field(default_factory=list, examples=[["cause: puste pole"]])

    # Accounting travels with the result: a caller summing a run must not have to reach back into
    # the client for what a given call cost.
    prompt_tokens:     int   = Field(default=0, examples=[4820])
    completion_tokens: int   = Field(default=0, examples=[640])
    cost_usd:          float = Field(default=0.0, examples=[0.0080])
    latency_ms:        float = Field(default=0.0, examples=[3120.4])
    model:             str   = Field(default="", examples=["claude-haiku-4-5"])

    @property
    def ok(self) -> bool:
        """
        Description:
        Tells whether this ticket produced a valid artifact.

        Example args:
            (none)

        Example result:
            True
        """
        return self.ticket is not None
