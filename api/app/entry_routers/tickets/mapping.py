from app.agent_graphs.gate_close import GateCloseState
from app.agent_graphs.parse_ticket import ParseTicketState
from app.core_model.tickets.closed_ticket_report import ClosedTicketReport
from app.entry_routers.mapping import to_log_items, to_usage_item
from app.entry_routers.tickets.models import ClosedTicketResponse, RuleHitItem

# Stany końcowe bramki zamknięcia i grafu karty oraz raport serwisu korpusu na odpowiedź
# `POST /tickets/closed`. Osobno od trasy, bo trasa ma w sobie tylko kolejne kroki.


def to_closed_ticket_response(
    ticket_id:     str,                               # np. "41002"
    gate:          GateCloseState,                    # np. GateCloseState(…, output=Verdict(…))
    rules_version: int,                               # np. 1
    card:          ParseTicketState | None = None,    # np. None — bramka zablokowała
    report:        ClosedTicketReport | None = None,  # np. ClosedTicketReport(indexed=True, …)
) -> ClosedTicketResponse:
    """
    Description:
    Zamienia przebieg zamknięcia zgłoszenia na odpowiedź trasy: werdykt bramki z furtką i wersją
    reguł, co stało się w korpusie, zużycie modelu i log obu grafów. Bez karty i raportu to
    odpowiedź na blokadę. Numer zgłoszenia podaje trasa, bo stan bramki go nie niesie.

    Example args:
        ticket_id="41002"
        gate=GateCloseState(input_text="ZGŁOSZENIE 41002…", rules=["…"],
                            output=Verdict(verdict="pass"))
        rules_version=1
        card=ParseTicketState(…, output=ParsedTicket(ticket_id="41002", useful=True, …))
        report=ClosedTicketReport(ticket_id="41002", replaced=False, indexed=True, dropped_by=[])

    Example result:
        ClosedTicketResponse(ticket_id="41002", outcome="indexed", replaced=False,
                             verdict="pass", …, useful_reason="Wątek podaje przyczynę…")
    """
    verdict = gate.output

    # --- bramka zablokowała: karty nie ma, korpus bez zmian ---
    if card is None or report is None:
        blocked = ClosedTicketResponse(
            ticket_id     = ticket_id,
            outcome       = "blocked",
            replaced      = False,
            verdict       = verdict.verdict,
            reasons       = verdict.reasons,
            hint          = verdict.hint,
            rules_version = rules_version,
            usage         = to_usage_item(gate.usage),
            log           = to_log_items(gate.log),
        )

        return blocked

    # --- karta zapisana: przyjęta do indeksów albo odrzucona przez filtr ---
    dropped_by = [RuleHitItem(rule=hit.rule, evidence=hit.evidence) for hit in report.dropped_by]

    response = ClosedTicketResponse(
        ticket_id     = ticket_id,
        outcome       = "indexed" if report.indexed else "dropped",
        replaced      = report.replaced,
        verdict       = verdict.verdict,
        reasons       = verdict.reasons,
        hint          = verdict.hint,
        rules_version = rules_version,
        useful_reason = card.output.useful_reason,
        dropped_by    = dropped_by,
        usage         = to_usage_item(gate.usage.plus(card.usage)),
        log           = to_log_items(gate.log + card.log),
    )

    return response
