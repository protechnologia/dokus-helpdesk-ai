import json
from pathlib import Path

import pytest

from app.model.ticket_parsed import ParsedTicket
from app.service.filter_ticket_quality import filter_tickets

# The reference corpus and the labels measured against it. Both live under data/ (PII, so not in
# git) and both are meant to survive the corpus rebuild of stage 10 — this test is one reason why.
CORPUS_DIR  = Path("data/parsed/bielik-11b-golden200")
LABELS_FILE = Path("data/golden/bielik-11b-golden200.json")

# What the filter achieved when it was written (2026-08-13): 29 of 38 labelled rejections, no false
# positives. The floor sits below the measured value so ordinary drift does not fail the suite,
# while a filter that went QUIET — the failure mode this whole test exists for — lands far under it.
MIN_LABELLED_DROPS = 25

# False positives are the expensive mistake: a filter that rejects good records teaches nobody
# anything and quietly shrinks the corpus. Measured at zero, and a couple of them would already be
# a different filter than the one that was measured.
MAX_FALSE_POSITIVES = 2


def _load_corpus() -> list[ParsedTicket]:
    """
    Description:
    Reads every artifact of the reference corpus, in sorted order.

    Example args:
        (none)

    Example result:
        [ParsedTicket(ticket_id="10012", …), …]
    """
    return [
        ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(CORPUS_DIR.glob("*.json"))
    ]


def _load_rejected_ids() -> set[str]:
    """
    Description:
    Reads the ticket ids the earlier review marked as carrying no reusable knowledge.

    Example args:
        (none)

    Example result:
        {"19596", "27348", …}
    """
    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))

    return {str(entry["ticket_id"]) for entry in labels["rejected"]}


@pytest.fixture(scope="module")
def measurement() -> tuple[int, int]:
    """
    Description:
    Runs the filter over the reference corpus once and returns (labelled drops, false positives).

    Skips rather than fails when the corpus is absent: data/ is not in git (it holds PII), so a
    fresh clone legitimately has none of it, and a red suite would say "the filter is broken" when
    it means "the data is elsewhere". Every other test in this project treats a missing
    prerequisite as a failure — here the prerequisite is deliberately not shipped.

    Example args:
        (none)

    Example result:
        (29, 0)
    """
    if not CORPUS_DIR.is_dir() or not LABELS_FILE.is_file():
        pytest.skip(f"brak korpusu referencyjnego ({CORPUS_DIR}) — dane nie są w repo")

    rejected = _load_rejected_ids()
    report   = filter_tickets(_load_corpus())
    dropped  = {verdict.ticket_id for verdict in report.dropped}

    return len(dropped & rejected), len(dropped - rejected)


def test_filter_still_recognises_hollow_records(measurement: tuple[int, int]) -> None:
    """Filter over the reference corpus → still drops most of the records the review rejected.

    THE POINT OF THIS FILE. The rules read text a language model wrote, so they fail by going
    QUIET: edit the escape phrases in the parsing prompt, or swap the model, and suddenly nothing
    matches — every record passes and the index fills with hollow entries while no other test
    notices. This one fails instead."""
    labelled_drops, _ = measurement

    assert labelled_drops >= MIN_LABELLED_DROPS, (
        f"filtr odrzuca {labelled_drops} z zaetykietowanych rekordów, oczekiwane >= "
        f"{MIN_LABELLED_DROPS} — czy zmienił się prompt parsujący albo model?"
    )


def test_filter_does_not_reject_good_records(measurement: tuple[int, int]) -> None:
    """Filter over the reference corpus → hardly any record the review kept is dropped.

    False alarms hurt more than misses here: a rejected record is gone from the index without
    anyone noticing, while a missed one merely takes up space."""
    _, false_positives = measurement

    assert false_positives <= MAX_FALSE_POSITIVES, (
        f"filtr odrzucił {false_positives} rekordów uznanych za dobre, dozwolone "
        f"{MAX_FALSE_POSITIVES} — reguła stała się za szeroka"
    )
