"""
Description:
Zmyślone raporty masowego importu do testów komendy `helpdesk tickets import`. Pakiet helpera tego
pliku nie wystawia — test importuje próbki z tego modułu.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.core_model.tickets.ticket_import_failure import TicketImportFailure
from app.core_model.tickets.tickets_import_report import TicketsImportReport

# Skrót promptu w próbkach: 64 znaki, żeby komenda mogła pokazać jego początek.
SAMPLE_DIGEST = "308c1c483d78" + "0" * 52


def sample_import_report(
    todo:     int                           = 25,   # np. 25 — zgłoszeń do zrobienia
    parsed:   int                           = 0,    # np. 10 — zapisanych kart
    failed:   Sequence[TicketImportFailure] = (),   # np. [TicketImportFailure(…)]
    cost_usd: float                         = 0.0,  # np. 0.05
) -> TicketsImportReport:
    """
    Description:
    Zwraca raport importu z 30 zgłoszeniami w eksporcie, po 2 w toku, 2 mailowe i 1 z kartą,
    ruszony 30 s temu, z podanym postępem.

    Example args:
        todo=25
        parsed=10
        cost_usd=0.05

    Example result:
        TicketsImportReport(files=30, todo=25, parsed=10, cost_usd=0.05, …)
    """
    report = TicketsImportReport(
        started_at     = datetime.now(UTC) - timedelta(seconds=30),
        model          = "gpt-6.1-sol",
        prompt_digest  = SAMPLE_DIGEST,
        files          = 30,
        skipped_open   = 2,
        skipped_mail   = 2,
        already_carded = 1,
        todo           = todo,
        parsed         = parsed,
        useful         = parsed,
        failed         = list(failed),
        cost_usd       = cost_usd,
    )

    return report
