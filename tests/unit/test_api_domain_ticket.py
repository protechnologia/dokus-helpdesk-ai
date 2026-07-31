import pytest
from pydantic import ValidationError

from app.domain.ticket import NO_VALUE, NOT_APPLICABLE, ParsedTicket

# A record carrying real content, used as the starting point every test varies from.
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


def test_valid_ticket_is_accepted() -> None:
    """Record with every field filled → validates and keeps the values it was given."""
    ticket = ParsedTicket(**VALID_TICKET)

    assert ticket.ticket_id  == "33644"
    assert ticket.resolution == "naprawione"


def test_record_of_pure_exits_is_valid() -> None:
    """Every optional field set to its explicit exit → valid (a normal state, not a defect)."""
    ticket = ParsedTicket(
        **{
            **VALID_TICKET,
            "cause":             NO_VALUE,
            "solution":          NO_VALUE,
            "symptoms":          NOT_APPLICABLE,
            "error_codes":       [],
            "questions_summary": NO_VALUE,
        }
    )

    assert ticket.cause    == NO_VALUE
    assert ticket.symptoms == NOT_APPLICABLE


def test_questions_summary_defaults_to_the_explicit_exit() -> None:
    """Field omitted entirely → defaults to `brak` (empty in most records is the norm)."""
    payload = {key: value for key, value in VALID_TICKET.items() if key != "questions_summary"}

    assert ParsedTicket(**payload).questions_summary == NO_VALUE


@pytest.mark.parametrize("field", ["component", "problem", "symptoms", "cause", "solution"])
def test_blank_text_is_rejected(field: str) -> None:
    """Whitespace-only text → ValidationError (a skipped field must not look answered)."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, field: "   "})


def test_surrounding_whitespace_is_stripped() -> None:
    """Value padded with spaces → stored trimmed, so the same text never yields two vectors."""
    ticket = ParsedTicket(**{**VALID_TICKET, "problem": "  Drukarka nie drukuje  "})

    assert ticket.problem == "Drukarka nie drukuje"


def test_unknown_field_is_rejected() -> None:
    """Key outside the schema → ValidationError, never a silent drop (the LLM run is one-off)."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, "severity": "wysoka"})


def test_resolution_outside_the_vocabulary_is_rejected() -> None:
    """Outcome kind absent from the vocabulary → ValidationError (typos must not enter)."""
    with pytest.raises(ValidationError):
        ParsedTicket(**{**VALID_TICKET, "resolution": "zamkniete-bo-tak"})


def test_record_from_another_vocabulary_version_is_rejected() -> None:
    """Version differing from the shipped vocabulary → ValidationError naming both versions."""
    with pytest.raises(ValidationError) as exc:
        ParsedTicket(**{**VALID_TICKET, "resolution_vocabulary_version": 99})

    # The message must say the vocabulary is out of step, not merely "invalid value" — otherwise
    # a whole re-parsed corpus looks like a thousand unrelated errors.
    assert "99" in str(exc.value)


def test_embedding_text_joins_only_problem_and_symptoms() -> None:
    """Embedding text → problem + symptoms, in that order, and nothing else."""
    ticket = ParsedTicket(**VALID_TICKET)

    assert ticket.embedding_text() == f"{ticket.problem}\n{ticket.symptoms}"


def test_embedding_text_excludes_the_solution() -> None:
    """Embedding text → carries no trace of `solution` (it would mix two signals in one vector)."""
    ticket = ParsedTicket(**{**VALID_TICKET, "solution": "UNIKATOWAFRAZA"})

    assert "UNIKATOWAFRAZA" not in ticket.embedding_text()


def test_artifact_records_the_vocabulary_version() -> None:
    """Serialised record → carries the vocabulary version, so a later edit stays traceable."""
    dumped = ParsedTicket(**VALID_TICKET).model_dump()

    assert dumped["resolution_vocabulary_version"] == 1
