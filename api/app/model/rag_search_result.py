from pydantic import BaseModel, Field

from app.model.ticket_parsed import ParsedTicket
from app.retrieval import TicketHit


class SearchResult(BaseModel):
    """
    Description:
    What one search produced: the hits that cleared the threshold, plus the parsed form of the
    query they were found with.

    Do czego:
    A domain model, unlike the transport `TicketHit` it carries — it is what the HTTP handler and
    the CLI both render, and what stage 6 reads to build a proposal. The parsed query travels with
    it because callers need to show WHAT was actually searched for: the model rewrote a raw thread
    into `problem` + `symptoms`, and an unexpected reading of the ticket is the first thing that
    explains a surprising result.

    Flow:
        1. `RagSearcher.search()` fills it after parsing, embedding and querying.
        2. `POST /search` maps it onto the API model; the CLI prints it.
        3. Stage 6 reads `hits` to build the generation prompt.

    `dropped_below_threshold` is a count rather than the records themselves. It answers the one
    question a caller has about a short result — "was there nothing, or did the threshold cut it?"
    — without carrying payloads nobody is allowed to use.
    """

    query:                  ParsedTicket
    hits:                   list[TicketHit] = Field(default_factory=list)
    dropped_below_threshold: int            = Field(default=0, examples=[3])

    @property
    def is_empty(self) -> bool:
        """
        Description:
        Whether the search found nothing usable. Its own property because "no hits" is a
        documented product state — the "new kind of problem" answer, correct for 47% of the
        corpus (singletons) — rather than a failure to report.

        Example args:
            (none)

        Example result:
            False
        """
        return not self.hits
