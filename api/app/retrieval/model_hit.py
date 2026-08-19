from pydantic import BaseModel, ConfigDict, Field


class TicketHit(BaseModel):
    """
    Description:
    One record as Qdrant returned it from a search: its similarity score plus the payload that was
    stored with it. A TRANSPORT model, like `TicketPoint` beside it — it describes what comes back
    over the wire from one particular service, so swapping the vector database touches this
    directory and nothing else (CLAUDE.md -> "Warstwy kodu").

    Do czego:
    The read-side counterpart of `TicketPoint`. Everything downstream — the threshold, the
    collapsing of agreeing hits, the generation prompt — works on these rather than on Qdrant's
    JSON, so no caller ever learns the wire shape.

    Flow:
        1. `from_qdrant()` reads one entry of a query response.
        2. The client returns a list of them, already ordered by score.
        3. The search service filters by threshold; stage 5 collapses agreeing ones.

    The payload is kept whole rather than unpacked into fields. It is written by `TicketPoint` and
    read by the generation prompt, and a second place spelling out those keys would be a second
    place to forget one — the shape is already fixed by `extra="forbid"` on the write side.
    """

    # Same reasoning as on `TicketPoint`: an unexpected key means the wire shape drifted, and that
    # is a mistake to surface rather than an extension to absorb.
    model_config = ConfigDict(extra="forbid")

    point_id: str   = Field(examples=["3f2a1c9e-5d7b-5a11-8e44-1c2b3d4e5f60"])
    score:    float = Field(examples=[0.87])
    payload:  dict  = Field(examples=[{"ticket_id": "33644", "component": "ePUAP"}])

    @property
    def ticket_id(self) -> str:
        """
        Description:
        The source ticket id this hit came from. Read off the payload because that is where it is
        stored — `point_id` is a UUID derived from it and cannot be reversed.

        Example args:
            (none)

        Example result:
            "33644"
        """
        return self.payload.get("ticket_id", "")

    @classmethod
    def from_qdrant(
        cls,
        entry: dict,  # e.g. {"id": "3f2a…", "score": 0.87, "payload": {"ticket_id": "33644"}}
    ) -> "TicketHit":
        """
        Description:
        Reads one entry of a Qdrant query response.

        Defaults rather than indexing: a response shape we do not recognise must fail as OUR
        problem at the boundary, not as a KeyError three layers down in the search service.

        Example args:
            entry={"id": "3f2a1c9e-…", "score": 0.87, "payload": {"ticket_id": "33644"}}

        Example result:
            TicketHit(point_id="3f2a1c9e-…", score=0.87, payload={"ticket_id": "33644"})
        """
        return cls(
            point_id = str(entry.get("id", "")),
            score    = float(entry.get("score", 0.0)),
            # An empty payload is a legitimate answer (a point written without one), so it must not
            # be confused with a missing key — both end up as {} and neither is an error here.
            payload  = entry.get("payload") or {},
        )
