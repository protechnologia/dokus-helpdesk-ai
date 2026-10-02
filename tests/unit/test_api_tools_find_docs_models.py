import pytest
from pydantic import ValidationError

from app.tools.find_docs import FindDocsQuery, FoundDoc


def make_found(
    version: str = "4.12",  # e.g. "" to provoke a refusal
) -> FoundDoc:
    """
    Description:
    Builds a valid documentation fragment, so each test changes only the field it is about.

    Example args:
        version="4.12"

    Example result:
        FoundDoc(fragment_id="doc-7", score=0.62, document="…", version="4.12", text="…")
    """
    return FoundDoc(
        fragment_id = "doc-7",
        score       = 0.62,
        document    = "Instrukcja administratora — e-Doręczenia",
        version     = version,
        text        = "Aby nadać uprawnienie do kancelarii, otwórz Ustawienia → Uprawnienia.",
    )


def test_an_empty_query_is_refused() -> None:
    """A query with no text → ValidationError: there is nothing to match the fragments against."""
    with pytest.raises(ValidationError):
        FindDocsQuery(text="")


def test_a_fragment_without_its_release_is_refused() -> None:
    """A fragment with no version → ValidationError: an instruction for an unknown release cannot
    be told apart from an outdated one."""
    with pytest.raises(ValidationError):
        make_found(version="")


def test_a_valid_fragment_keeps_its_release() -> None:
    """A complete fragment → kept with its release, the field generation needs to flag staleness."""
    assert make_found().version == "4.12"
