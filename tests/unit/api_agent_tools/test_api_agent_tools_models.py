from datetime import date

import pytest
from pydantic import ValidationError

from app.agent_tools import SourceRef


def make_ref(
    source:  str = "tickets",                                # e.g. "docs"
    item_id: str = "33644",                                  # e.g. "doc-7"
    title:   str = "Wysyłka przez ePUAP kończy się błędem",  # e.g. "Instrukcja administratora 4.12"
) -> SourceRef:
    """
    Description:
    Builds a valid source reference, so each test changes only the one field it is about.

    Example args:
        source="tickets"
        item_id="33644"
        title="Wysyłka przez ePUAP kończy się błędem"

    Example result:
        SourceRef(source="tickets", item_id="33644", title="Wysyłka…", date=date(2026, 3, 14))
    """
    return SourceRef(
        source  = source,
        item_id = item_id,
        title   = title,
        date    = date(2026, 3, 14),
    )


def test_key_tells_sources_apart() -> None:
    """The same id from two tools → two different keys, so de-duplicating the sources of one
    answer never merges a ticket with a documentation fragment."""
    ticket   = make_ref(source="tickets", item_id="33644")
    fragment = make_ref(source="docs",    item_id="33644")

    assert ticket.key   == "tickets:33644"
    assert ticket.key   != fragment.key


def test_a_ref_carries_no_score() -> None:
    """A reference with a score → ValidationError: sources are what the model read by id, and a
    read has no similarity. The score is shown to the model by the search, never to the reader."""
    with pytest.raises(ValidationError):
        SourceRef(source="docs", item_id="doc-7", title="Instrukcja administratora", score=0.87)


def test_a_ref_may_have_no_date() -> None:
    """A reference without a date → accepted: a documentation section may come from a release
    with no date stated."""
    ref = SourceRef(source="docs", item_id="doc-7", title="Instrukcja administratora 4.12")

    assert ref.date is None


@pytest.mark.parametrize("field", ["source", "item_id", "title"])
def test_empty_identity_is_refused(field: str) -> None:
    """An empty source, id or title → ValidationError: a source nobody can identify cannot be
    cited, and one nobody can recognise cannot be checked."""
    with pytest.raises(ValidationError):
        make_ref(**{field: ""})


def test_an_unknown_field_is_refused() -> None:
    """A key outside the contract → ValidationError, the same reasoning as on ParsedTicket: drift
    is a mistake to surface, not an extension to absorb."""
    with pytest.raises(ValidationError):
        SourceRef(source="tickets", item_id="33644", title="x", rank=1)
