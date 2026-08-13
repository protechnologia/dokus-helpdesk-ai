import pytest

from app.model.ticket_parsed import ParsedTicket
from app.service.filter_ticket_quality import (
    MIN_RECORDS_FOR_DROP_RATE,
    drop_rate_warning,
    evaluate_ticket,
    filter_tickets,
)
from app.service.filter_ticket_quality_rules import RULES

# A record carrying real content, varied per test. Same starting point as the ParsedTicket tests, so
# a schema change breaks both files the same way instead of leaving this one testing a dead shape.
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


def _ticket(**overrides: object) -> ParsedTicket:
    """
    Description:
    Builds a record from the valid baseline with per-test overrides.

    Example args:
        solution="Brak rozstrzygnięcia w wątku."

    Example result:
        ParsedTicket(ticket_id="33644", solution="Brak rozstrzygnięcia w wątku.", …)
    """
    return ParsedTicket(**{**VALID_TICKET, **overrides})


# --- what the rule drops ------------------------------------------------------------------

@pytest.mark.parametrize(
    "solution",
    [
        "brak",                                                     # the schema's own escape value
        "nie dotyczy",                                              # the other escape value
        "Brak rozstrzygnięcia w wątku.",                            # escape phrase plus filler
        "Brak rozstrzygnięcia - problem pozostaje nierozwiązany.",   # still nothing done
        "Rozwiązane do zamknięcia (brak szczegółów co do sposobu)",  # admission mid-sentence
    ],
)
def test_hollow_solution_is_dropped(solution: str) -> None:
    """Solution that admits to nothing and adds little else → dropped, with the text as evidence."""
    verdict = evaluate_ticket(_ticket(solution=solution))

    assert not verdict.keep
    assert verdict.reasons == ["no_resolution"]
    assert verdict.hits[0].evidence


# --- what the rule must NOT drop ----------------------------------------------------------

@pytest.mark.parametrize(
    "solution",
    [
        # A refusal is the most valuable class in this corpus — it says what NOT to attempt. It
        # opens with the same word as an empty record, so only the amount of text tells them apart.
        "Brak możliwości wygenerowania ZPO w tej sytuacji. Klient musi zaakceptować brak"
        " potwierdzenia, ponieważ operator nie wystawia go dla przesyłek nierejestrowanych.",
        # "No change in the system" plus an explanation: the client learns how it actually works.
        "Brak zmian w systemie. Klient otrzymał wyjaśnienie, jak działa mechanizm eksportu danych"
        " i dlaczego kolumny pojawiają się w tej kolejności.",
        # `brak` as a PREFIX of an ordinary adjective, in a record describing work that was done.
        # This one cost a false positive until the pattern moved to whole-word matching.
        "Dodano brakujące ustawienie systemowe. Wykonuje dostawca.",
        "Konsultant utworzył brakujące katalogi do końca roku i potwierdził, że błąd znika.",
    ],
)
def test_solution_with_content_is_kept(solution: str) -> None:
    """Solution whose "brak" opens a real statement → kept; emptiness is short, content is not."""
    assert evaluate_ticket(_ticket(solution=solution)).keep


def test_ordinary_solution_is_kept() -> None:
    """Solution with no escape phrase at all → kept without any rule firing."""
    verdict = evaluate_ticket(_ticket())

    assert verdict.keep
    assert verdict.hits == []


# --- report -------------------------------------------------------------------------------

def test_report_splits_kept_from_dropped() -> None:
    """Mixed corpus → each record on the right side of the split."""
    report = filter_tickets(
        [
            _ticket(ticket_id="1"),
            _ticket(ticket_id="2", solution="brak"),
            _ticket(ticket_id="3"),
        ]
    )

    assert [v.ticket_id for v in report.kept]    == ["1", "3"]
    assert [v.ticket_id for v in report.dropped] == ["2"]


def test_report_counts_drops_per_reason() -> None:
    """Report groups drops by rule → a rule rejecting the wrong records is visible, which a single
    total would hide."""
    report = filter_tickets([_ticket(ticket_id="1", solution="brak"), _ticket(ticket_id="2")])

    assert report.by_reason() == {"no_resolution": 1}


def test_report_lists_ticket_ids_per_rule() -> None:
    """Report names the tickets a rule dropped → stage 11 needs the tickets, not a count."""
    report = filter_tickets([_ticket(ticket_id="19596", solution="brak"), _ticket(ticket_id="2")])

    assert report.ticket_ids_for("no_resolution") == ["19596"]


def test_empty_corpus_is_an_empty_report() -> None:
    """No records → empty report, not an error: an unbuilt corpus is a legitimate state."""
    report = filter_tickets([])

    assert report.verdicts == []
    assert report.by_reason() == {}


# --- drop-rate warning: the guard against the rules going silent ---------------------------

def test_silent_filter_is_reported() -> None:
    """Large corpus with almost nothing dropped → warning. This is the failure mode the rules
    cannot detect themselves: a changed prompt or model, and every record suddenly passes while
    nothing turns red."""
    report = filter_tickets([_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)])

    assert "reguły" in (drop_rate_warning(report) or "")


def test_plausible_drop_rate_is_silent() -> None:
    """Corpus dropping about as much as every measurement predicts → no warning."""
    tickets = [_ticket(ticket_id=str(i)) for i in range(MIN_RECORDS_FOR_DROP_RATE)]
    # Roughly the measured 19%, comfortably inside the tolerance.
    for i in range(MIN_RECORDS_FOR_DROP_RATE // 5):
        tickets[i] = _ticket(ticket_id=str(i), solution="brak")

    assert drop_rate_warning(filter_tickets(tickets)) is None


def test_small_batch_never_warns() -> None:
    """Handful of records, none dropped → silence. A share means nothing at this size, and the
    single-ticket runtime call is exactly this case: 0% dropped is the CORRECT outcome there."""
    report = filter_tickets([_ticket()])

    assert drop_rate_warning(report) is None


# --- the rule registry --------------------------------------------------------------------

def test_every_rule_is_reachable_by_name() -> None:
    """Each rule in RULES reports under its own function name → the report groups by that name, so
    a rule that cannot be named cannot be counted. Parametrised over the registry rather than a
    hardcoded count, because adding a rule must not mean editing this test."""
    for rule in RULES:
        assert rule.__name__
        assert rule.__doc__, f"{rule.__name__} bez docstringa"
