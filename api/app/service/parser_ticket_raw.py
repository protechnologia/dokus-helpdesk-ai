import json
from datetime import date as Date
from pathlib import Path

from app.model.ticket_raw import RawTicket
from app.model.ticket_raw_comment import RawComment
from app.util.html import strip_html

# Source timestamps are MySQL datetimes; only the date half reaches the artifact.
SOURCE_DATETIME_LENGTH = len("2026-06-23")


def load_raw_ticket(path: Path) -> RawTicket:   # e.g. Path("data/raw/zgloszenie-33644.json")
    """
    Description:
    Reads one export file from `data/raw/` and normalises it. Every HTML field is stripped here,
    so nothing downstream has to know the source stores markup.

    Example args:
        path=Path("data/raw/zgloszenie-33644.json")

    Example result:
        RawTicket(ticket_id="33644", date=date(2026, 6, 23), subject="Błąd wysyłki", …)

    Raises:
        KeyError: the file lacks the shape produced by scripts/export_raw_tickets.py
        ValueError: the file is not valid JSON, or the timestamp is not a date we can read
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    ticket  = payload["zgloszenie"]

    return RawTicket(
        ticket_id = str(ticket["id"]),
        # "2026-06-23 11:45:05" -> date(2026, 6, 23); the time of day never reaches the artifact.
        date      = Date.fromisoformat(ticket["created_at"][:SOURCE_DATETIME_LENGTH]),
        category  = ticket.get("kategoria") or "",
        subject   = strip_html(ticket.get("czego_dotyczy") or ""),
        body      = strip_html(ticket.get("szczegolowy_opis") or ""),
        # `or []` rather than a `get()` default: the export writes the key with a null value for a
        # ticket nobody ever commented on, and a default only applies when the key is ABSENT.
        # 29 of the 1825 exported tickets are like this — the "no supplier comment at all" class
        # CLAUDE.md names as a signal of a record carrying no knowledge.
        comments  = [
            RawComment(
                kind       = comment.get("typ") or "",
                role       = comment.get("autor_rola") or "",
                created_at = comment.get("created_at") or "",
                body       = strip_html(comment.get("tresc") or ""),
            )
            for comment in payload.get("komentarze") or []
        ],
    )
