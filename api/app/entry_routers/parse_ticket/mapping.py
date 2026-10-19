from app.agent_graphs.parse_ticket import ParseTicketState
from app.entry_routers.mapping import to_log_items, to_usage_item
from app.entry_routers.parse_ticket.models import TicketCard

# Stan końcowy grafu `parse_ticket` na odpowiedź `POST /parse-ticket`. Osobno od trasy, bo tę
# samą odpowiedź złoży każda droga, którą trasa oddaje wynik.


def to_ticket_card(
    final: ParseTicketState,  # np. ParseTicketState(…, output=ParsedTicket(ticket_id="41002", …))
) -> TicketCard:
    """
    Description:
    Zamienia stan końcowy grafu `parse_ticket` na kartę zgłoszenia z zużyciem modelu i logiem
    przebiegu, pole po polu. Wersja słownika rozstrzygnięć to metadane artefaktu, więc do
    odpowiedzi nie idzie.

    Example args:
        final=ParseTicketState(input_text="ZGŁOSZENIE 41002…", ticket_id="41002", …,
                               output=ParsedTicket(ticket_id="41002", component="ePUAP", …))

    Example result:
        TicketCard(ticket_id="41002", component="ePUAP", problem="Wysyłka kończy się błędem", …)
    """
    card = final.output

    response = TicketCard(
        ticket_id         = card.ticket_id,
        date              = card.date,
        component         = card.component,
        problem           = card.problem,
        symptoms          = card.symptoms,
        error_codes       = card.error_codes,
        cause             = card.cause,
        solution          = card.solution,
        resolution        = card.resolution,
        questions_summary = card.questions_summary,
        usage             = to_usage_item(final.usage),
        log               = to_log_items(final.log),
    )

    return response
