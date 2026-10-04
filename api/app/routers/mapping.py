from datetime import date as Date

from app.agent_tools import SourceRef
from app.model.ticket_raw import RawTicket
from app.model.ticket_raw_comment import RawComment
from app.routers.models import SourceItem, TicketRequest

# Mapowanie modeli API na domenowe i z powrotem, wspólne dla tras. Pisane ręcznie, nie kopiowaniem
# pól hurtem: oba modele wolno rozjechać, a automat przekazałby dalej wszystko, co API akurat
# przyjmuje (CLAUDE.md -> „Warstwy kodu").

# Rola komentarza, gdy wołający jej nie podał — wątek jest wtedy uboższy, ale nie błędny.
UNKNOWN_ROLE = "nieznany"

# W miejscu znacznika czasu, którego źródło nie podało; znaczenie niesie kolejność komentarzy.
UNKNOWN_TIME = ""


def to_raw_ticket(
    request: TicketRequest,  # np. TicketRequest(ticket_id="41002", body="Nie działa wysyłka…")
) -> RawTicket:
    """
    Description:
    Zamienia zgłoszenie z żądania na `RawTicket`, czyli ten sam kształt, z którego parsowano
    korpus; `as_thread()` daje z niego tekst wejściowy grafów.

    Example args:
        request=TicketRequest(ticket_id="41002", body="Nie mogę wysłać pisma przez ePUAP.")

    Example result:
        RawTicket(ticket_id="41002", date=date(2026, 8, 19), body="Nie mogę wysłać pisma…")
    """
    ticket = RawTicket(
        ticket_id = request.ticket_id,
        # Zgłoszenie w toku jest z definicji świeże, więc brak daty znaczy „dziś".
        date      = request.date or Date.today(),
        category  = request.category,
        subject   = request.subject,
        body      = request.body,
        comments  = [
            RawComment(
                # `kind` to stan przepływu w bazie ŹRÓDŁOWEJ — w przychodzącym wątku nic nie znaczy.
                kind       = "zwyczajny",
                role       = comment.role or UNKNOWN_ROLE,
                created_at = comment.created_at or UNKNOWN_TIME,
                body       = comment.body,
            )
            for comment in request.comments
        ],
    )

    return ticket


def to_source_items(
    sources: list[SourceRef],  # np. [SourceRef(source="tickets", item_id="33644", …)]
) -> list[SourceItem]:
    """
    Description:
    Zamienia źródła ze stanu grafu na model API, pole po polu.

    Example args:
        sources=[SourceRef(source="tickets", item_id="33644", title="…", score=0.87)]

    Example result:
        [SourceItem(source="tickets", item_id="33644", title="…", score=0.87, date=None)]
    """
    items = [
        SourceItem(
            source  = ref.source,
            item_id = ref.item_id,
            title   = ref.title,
            score   = ref.score,
            date    = ref.date,
        )
        for ref in sources
    ]

    return items
