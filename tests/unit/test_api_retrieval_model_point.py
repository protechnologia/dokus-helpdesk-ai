import uuid

from app.model.ticket_parsed import ParsedTicket
from app.retrieval import VECTOR_PROBLEM, VECTOR_STS, TicketPoint, point_id_for

# The same starting record the ParsedTicket tests vary from, so a schema change breaks both files
# in the same way rather than leaving this one testing a shape that no longer exists.
VALID_TICKET = {
    "ticket_id":                     "33644",
    "date":                          "2026-03-14",
    "component":                     "ePUAP",
    "problem":                       "Wysyłka przez ePUAP kończy się błędem komunikacji",
    "symptoms":                      "Po kliknięciu Wyślij pojawia się komunikat o braku sieci",
    "error_codes":                   ["ERR-4210"],
    "cause":                         "Certyfikat bez uprawnienia AddDocumentToSign",
    "solution":                      "Wygenerowano certyfikat z właściwym uprawnieniem.",
    "resolution":                    "naprawione",
    "resolution_vocabulary_version": 1,
    "questions_summary":             "pytano o wersję przeglądarki",
}

# Two distinguishable vectors: assertions must be able to say WHICH one landed in which slot,
# which a pair of identical lists could not.
VECTOR_A = [0.1, -0.2, 0.3]
VECTOR_B = [0.9, 0.8, -0.7]


def _point(**overrides: object) -> TicketPoint:
    """
    Description:
    Builds a point from the valid record, with per-test field overrides. One helper because this
    file has one axis: the mapping from a parsed ticket to what Qdrant stores.

    Example args:
        ticket_id="33645"

    Example result:
        TicketPoint(point_id="…", payload={"ticket_id": "33645", …})
    """
    ticket = ParsedTicket(**{**VALID_TICKET, **overrides})

    return TicketPoint.from_ticket(
        ticket         = ticket,
        vector_problem = VECTOR_A,
        vector_sts     = VECTOR_B,
    )


def test_point_id_is_a_uuid() -> None:
    """Source ticket id (a string like "33644") → a UUID, the only id shape Qdrant accepts."""
    # Parsing is the assertion: uuid.UUID() rejects anything that is not one.
    assert uuid.UUID(point_id_for("33644"))


def test_point_id_is_stable_across_calls() -> None:
    """Same ticket id twice → same point id; this is what makes a rebuild overwrite rather than
    duplicate the corpus."""
    assert point_id_for("33644") == point_id_for("33644")


def test_point_id_is_a_golden_value() -> None:
    """Known ticket id → this exact UUID. Guards the frozen namespace: changing it re-scatters
    every id, so the next rebuild would duplicate the whole corpus instead of replacing it — a
    regression nothing else in the suite would notice."""
    assert point_id_for("33644") == "df3b51f3-9eac-56f3-9f28-6253f23dd731"


def test_different_tickets_get_different_ids() -> None:
    """Two ticket ids → two point ids (a collision would silently drop one record)."""
    assert point_id_for("33644") != point_id_for("33645")


def test_payload_carries_every_generation_field() -> None:
    """Parsed ticket → payload holding everything the generation prompt reads."""
    payload = _point().payload

    # Named one by one rather than compared as a set: this list IS the contract with the
    # generation prompt, so a field silently dropped from the payload must fail here.
    assert payload["ticket_id"]         == "33644"
    assert payload["component"]         == "ePUAP"
    assert payload["problem"]           == VALID_TICKET["problem"]
    assert payload["symptoms"]          == VALID_TICKET["symptoms"]
    assert payload["error_codes"]       == ["ERR-4210"]
    assert payload["cause"]             == VALID_TICKET["cause"]
    assert payload["solution"]          == VALID_TICKET["solution"]
    assert payload["resolution"]        == "naprawione"
    assert payload["questions_summary"] == VALID_TICKET["questions_summary"]
    assert payload["resolution_vocabulary_version"] == 1


def test_payload_date_is_an_iso_string() -> None:
    """date → ISO text, not a date object: JSON has no date type and Qdrant sorts these
    correctly."""
    assert _point().payload["date"] == "2026-03-14"


def test_wire_shape_names_both_vectors() -> None:
    """to_qdrant() → vectors keyed by NAME, each carrying the vector it was given. A bare list
    here would be rejected by a multi-vector collection, and a swapped pair would put queries and
    dedup into each other's vector space — invisible afterwards, because both still look valid."""
    vectors = _point().to_qdrant()["vector"]

    assert vectors[VECTOR_PROBLEM] == VECTOR_A
    assert vectors[VECTOR_STS]     == VECTOR_B


def test_wire_shape_carries_id_and_payload() -> None:
    """to_qdrant() → the three keys Qdrant's upsert expects, with the point id among them."""
    wire = _point().to_qdrant()

    assert set(wire)      == {"id", "vector", "payload"}
    assert wire["id"]     == point_id_for("33644")
    assert wire["payload"]["ticket_id"] == "33644"
