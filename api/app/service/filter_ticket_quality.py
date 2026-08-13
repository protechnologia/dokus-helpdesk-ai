from app.model.filter_quality_report import QualityReport
from app.model.filter_quality_verdict import QualityVerdict, RuleHit
from app.model.ticket_parsed import ParsedTicket
from app.service.filter_ticket_quality_rules import RULES

# Share of the corpus the filter is expected to drop. Measured twice on different samples: 19% of
# the 200-record reference set, 25-26% over 661 records reviewed earlier. Anything far below that
# means the rules stopped matching what the parser writes, not that the corpus got better.
EXPECTED_DROP_RATE = 0.19

# How far the drop rate may fall before the run says so. Wide on purpose — the point is catching a
# filter that went SILENT (a changed prompt, a swapped model), not policing normal variation.
DROP_RATE_TOLERANCE = 0.5

# Below this many records a drop rate says nothing: with a handful of tickets a single decision
# swings it by tens of percent. Without this floor the check would fire on every healthy small
# batch — including a single-ticket runtime call, where 0% dropped is the CORRECT outcome.
MIN_RECORDS_FOR_DROP_RATE = 50


def evaluate_ticket(
    ticket: ParsedTicket,  # e.g. ParsedTicket(ticket_id="19596", …)
) -> QualityVerdict:
    """
    Description:
    Judges ONE record and returns the verdict with the evidence collected. This is the entry point
    for both callers: the batch indexing run of stage 4 and a runtime check on a single closed
    ticket. `filter_tickets()` below is this function over a corpus plus the statistics a batch run
    needs — nothing more.

    All rules run, none short-circuits: a record may be hollow for more than one reason, and the
    report groups drops per rule, so stopping at the first hit would understate whichever rule
    happens to sit later in the tuple.

    Not to be confused with the CLOSING GATE of stage 9. Both look at the same axis — is there a
    problem and a resolution — but they answer different questions ("is this worth keeping in the
    index" against "may this be closed"), return different shapes, and the gate calls an LLM. This
    is a candidate for a cheap pre-filter in front of that gate, never a replacement for it.

    Example args:
        ticket=ParsedTicket(ticket_id="19596", solution="Brak rozstrzygnięcia w wątku.", …)

    Example result:
        QualityVerdict(ticket_id="19596", hits=[RuleHit(rule="no_resolution", evidence="Brak…")])
    """
    hits = []

    for rule in RULES:
        evidence = rule(ticket.solution)

        if evidence is not None:
            hits.append(RuleHit(rule=rule.__name__, evidence=evidence))

    return QualityVerdict(ticket_id=ticket.ticket_id, hits=hits)


def filter_tickets(
    tickets: list[ParsedTicket],  # e.g. [ParsedTicket(ticket_id="33644", …)]
) -> QualityReport:
    """
    Description:
    Judges a whole corpus and returns the report the indexing run prints.

    Takes records rather than a directory: reading and validating artifacts belongs to
    `validator_ticket_parsed`, and a filter that also walked the filesystem could not be measured
    against a hand-built list of edge cases.

    Example args:
        tickets=[ParsedTicket(ticket_id="33644", …), ParsedTicket(ticket_id="19596", …)]

    Example result:
        QualityReport(verdicts=[QualityVerdict(ticket_id="33644", hits=[]), …])
    """
    return QualityReport(verdicts=[evaluate_ticket(ticket) for ticket in tickets])


def drop_rate_warning(
    report: QualityReport,  # e.g. QualityReport(verdicts=[…])
) -> str | None:
    """
    Description:
    Returns a warning when the filter dropped far less of the corpus than every measurement leads
    us to expect, or None when the rate is plausible or the batch is too small to judge.

    Why this exists: the rules read text a language model wrote, so the way they fail is by going
    QUIET — a changed parsing prompt or a swapped model, and suddenly nothing matches, every record
    passes, and the index fills with hollow entries while nothing turns red. A count of what was
    dropped is the one signal that cannot fail the way the rules do, because it depends on no
    wording at all.

    Deliberately a warning, not an exception: a genuinely better corpus would trip it too, and
    aborting an indexing run over a statistic would be wrong.

    Example args:
        report=QualityReport(verdicts=[…])  # 200 records, 4 dropped

    Example result:
        "filtr odrzucił 2.0% korpusu, oczekiwane ~19% — sprawdź, czy reguły nadal pasują do
         artefaktów (zmiana promptu parsującego albo modelu?)"
    """
    # Too few records for a share to mean anything — including the single-ticket runtime call.
    if len(report.verdicts) < MIN_RECORDS_FOR_DROP_RATE:
        return None

    rate = len(report.dropped) / len(report.verdicts)

    if rate >= EXPECTED_DROP_RATE * DROP_RATE_TOLERANCE:
        return None

    return (
        f"filtr odrzucił {rate:.1%} korpusu, oczekiwane ~{EXPECTED_DROP_RATE:.0%} — sprawdź, "
        f"czy reguły nadal pasują do artefaktów (zmiana promptu parsującego albo modelu?)"
    )
