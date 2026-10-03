import pytest
from pydantic import ValidationError

from app.retrieval import TicketHit


def test_reads_a_qdrant_entry() -> None:
    """A query entry → TicketHit carrying its id, score and payload unchanged."""
    hit = TicketHit.from_qdrant(
        {"id": "3f2a1c9e", "score": 0.87, "payload": {"ticket_id": "33644", "cause": "brak"}}
    )

    assert hit.point_id  == "3f2a1c9e"
    assert hit.score     == 0.87
    assert hit.ticket_id == "33644"
    assert hit.payload["cause"] == "brak"


def test_payload_is_kept_whole() -> None:
    """Every payload key survives the read: the generation prompt reads fields this model never
    names, so unpacking into a fixed set would be a second place to forget one."""
    payload = {
        "ticket_id":         "33644",
        "date":              "2026-06-23",
        "component":         "ePUAP",
        "problem":           "Brak wizualizacji UPP",
        "symptoms":          "nie dotyczy",
        "error_codes":       "brak",
        "cause":             "brak",
        "solution":          "Wygenerowano podglądy ręcznie.",
        "resolution":        "naprawione",
        "questions_summary": "brak",
        "resolution_vocabulary_version": "1",
    }

    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": payload})

    assert hit.payload == payload


def test_a_point_without_a_payload_is_not_an_error() -> None:
    """A point written without a payload → empty dict rather than a crash: that is a legitimate
    state of the collection, and the search service decides what to do with it."""
    hit = TicketHit.from_qdrant({"id": "a", "score": 0.5, "payload": None})

    assert hit.payload   == {}
    assert hit.ticket_id == ""


def test_missing_score_reads_as_zero() -> None:
    """An entry without a score → 0.0, which every threshold rejects. A shape we do not recognise
    must not become a hit that outranks real ones."""
    hit = TicketHit.from_qdrant({"id": "a"})

    assert hit.score == 0.0


def test_an_unknown_field_is_refused() -> None:
    """Constructing with a key outside the contract → ValidationError. Same reasoning as on
    TicketPoint: a drifted wire shape is a mistake to surface, not an extension to absorb."""
    with pytest.raises(ValidationError):
        TicketHit(point_id="a", score=0.5, payload={}, vector=[0.1])
