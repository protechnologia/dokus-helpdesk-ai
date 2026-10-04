import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.model.ticket_parsed import ParsedTicket

# Namespace for deriving a point id from a `ticket_id`. Qdrant accepts only unsigned integers or
# UUIDs as point ids, while ours are source strings ("33644"), so one has to be derived from the
# other. UUID5 rather than a counter because the mapping must be a FUNCTION of the ticket id:
# `index rebuild` run twice has to land on the same points, otherwise a rebuild would duplicate
# the corpus instead of replacing it (CLAUDE.md -> stage 4.5, "two rebuilds give an identical
# collection"). The namespace value itself is arbitrary but FROZEN — changing it re-scatters every
# id and turns the next rebuild into a full duplicate.
POINT_ID_NAMESPACE = uuid.UUID("6f1d5a3c-6b8e-5e2a-9a44-0f2c6f9c1b77")

# Named vectors carried by every point. `problem` holds the passage-side embedding a runtime query
# is matched against; `sts` holds the symmetric one used for dedup and "similar cases".
#
# Both are built even though stage 3 measured `query→passage` as the better search mode: that
# measurement covered RAW queries only, while the argument for `sts→sts` was about PARSED ones —
# an axis that needs an LLM pass and has not been measured yet (CLAUDE.md -> "Embeddingi
# i prefiksy PolDense"). Dropping `sts` now would make re-adding it a full re-index.
VECTOR_PROBLEM = "problem"
VECTOR_STS     = "sts"


class TicketPoint(BaseModel):
    """
    Description:
    One record as Qdrant stores it: a point id, two named vectors and the payload an answer is
    later generated from. This is a TRANSPORT model — it lives beside the client rather than in
    `model/` because it describes what crosses the wire to one particular service (CLAUDE.md ->
    "Warstwy kodu"). Swapping the vector database should touch this directory and nothing else.

    Flow:
        1. `from_ticket()` derives it from a validated `ParsedTicket` plus its two vectors.
        2. `to_qdrant()` renders the wire shape Qdrant's upsert endpoint expects.
        3. The client posts batches of those; nothing else in the codebase knows the wire shape.

    What the payload carries and why: everything the generation prompt reads, and nothing the
    vector already holds. `solution` travels here rather than in the vector on purpose — we search
    by similarity of the PROBLEM, and a vector polluted with the answer mixes both signals. `date`
    is unconditional, because staleness, contradictions between records and seasonality all depend
    on it (CLAUDE.md -> "Twarde reguły promptu generacji").
    """

    # Payload keys are fixed by what the generation prompt reads, so an unknown one is a mistake
    # rather than an extension — same reasoning as `extra="forbid"` on ParsedTicket.
    model_config = ConfigDict(extra="forbid")

    point_id:       str         = Field(examples=["3f2a1c9e-5d7b-5a11-8e44-1c2b3d4e5f60"])
    vector_problem: list[float] = Field(examples=[[0.0123, -0.0456]])
    vector_sts:     list[float] = Field(examples=[[0.0987, -0.0654]])
    payload:        dict        = Field(examples=[{"ticket_id": "33644", "component": "ePUAP"}])

    @classmethod
    def from_ticket(
        cls,
        ticket:         ParsedTicket,  # e.g. ParsedTicket(ticket_id="33644", …)
        vector_problem: list[float],   # e.g. [0.0123, -0.0456] — from embed_passage()
        vector_sts:     list[float],   # e.g. [0.0987, -0.0654] — from embed_sts()
    ) -> "TicketPoint":
        """
        Description:
        Builds the point for one parsed ticket. The two vectors are passed in rather than computed
        here: embedding crosses a different process boundary, and a transport model that called
        another service would tie the two dependencies together.

        Example args:
            ticket=ParsedTicket(ticket_id="33644", …)
            vector_problem=[0.0123, -0.0456]
            vector_sts=[0.0987, -0.0654]

        Example result:
            TicketPoint(point_id="3f2a1c9e-…", payload={"ticket_id": "33644", …})
        """
        payload = {
            "ticket_id":         ticket.ticket_id,
            # ISO string rather than a date object: JSON has no date type, and Qdrant's range
            # filters sort ISO strings correctly, so the storage format is also the queryable one.
            "date":              ticket.date.isoformat(),
            "component":         ticket.component,
            "problem":           ticket.problem,
            "symptoms":          ticket.symptoms,
            "error_codes":       ticket.error_codes,
            # Carried even though it is not embedded: `cause` is what tells competing hits apart
            # when one symptom has several causes, and the generation prompt needs to see all of
            # them side by side (CLAUDE.md -> "Powtarza się objaw", consequence 5).
            "cause":             ticket.cause,
            "solution":          ticket.solution,
            "resolution":        ticket.resolution,
            "questions_summary": ticket.questions_summary,
            # Which vocabulary produced `resolution`. Travels with the record so a later edit of
            # the vocabulary stays traceable without re-reading the artifact from disk (rule 7).
            "resolution_vocabulary_version": ticket.resolution_vocabulary_version,
        }

        return cls(
            point_id       = point_id_for(ticket.ticket_id),
            vector_problem = vector_problem,
            vector_sts     = vector_sts,
            payload        = payload,
        )

    def to_qdrant(self) -> dict:
        """
        Description:
        Renders the wire shape of one point. Kept on the model so the client stays a transport —
        it batches and posts, it does not know how a record is laid out.

        Example args:
            (none)

        Example result:
            {"id": "3f2a1c9e-…", "vector": {"problem": […], "sts": […]}, "payload": {…}}
        """
        return {
            "id": self.point_id,
            # A dict rather than a bare list: that is what makes these NAMED vectors. Sending a
            # bare list into a multi-vector collection is rejected by Qdrant, which is the
            # intended outcome — it means a caller forgot which vector space it was writing to.
            "vector": {
                VECTOR_PROBLEM: self.vector_problem,
                VECTOR_STS:     self.vector_sts,
            },
            "payload": self.payload,
        }


def point_id_for(
    ticket_id: str,  # e.g. "33644"
) -> str:
    """
    Description:
    Maps a source ticket id onto the UUID Qdrant needs. A pure function of the input, so the same
    ticket always occupies the same point and a re-index overwrites rather than duplicates.

    A module-level function rather than a method: it is a stateless computation, and callers need
    it WITHOUT a point in hand — deleting a record by ticket id has no vectors to build one from
    (CLAUDE.md -> "Warstwy kodu", "funkcja czy klasa — rozstrzyga stan").

    Example args:
        ticket_id="33644"

    Example result:
        "3f2a1c9e-5d7b-5a11-8e44-1c2b3d4e5f60"
    """
    return str(uuid.uuid5(POINT_ID_NAMESPACE, ticket_id))
