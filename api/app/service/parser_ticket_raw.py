import json
from datetime import date as Date
from pathlib import Path

from app.model.ticket_raw import RawTicket
from app.model.ticket_raw_comment import RawComment
from app.util.html import strip_html

# Znaczniki czasu w źródle to datetime z MySQL; do artefaktu trafia tylko część z datą.
SOURCE_DATETIME_LENGTH = len("2026-06-23")


def load_raw_ticket(path: Path) -> RawTicket:   # np. Path("data/raw/zgloszenie-33644.json")
    """
    Description:
    Czyta jeden plik eksportu z `data/raw/` i go normalizuje. Każde pole HTML jest strippowane
    tutaj, więc nic dalej nie musi wiedzieć, że źródło trzyma znaczniki.

    Example args:
        path=Path("data/raw/zgloszenie-33644.json")

    Example result:
        RawTicket(ticket_id="33644", date=date(2026, 6, 23), subject="Błąd wysyłki", …)

    Raises:
        KeyError: plik nie ma kształtu, który wytwarza scripts/export_raw_tickets.py
        ValueError: plik nie jest poprawnym JSON-em albo znacznik czasu nie daje się odczytać
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    ticket  = payload["zgloszenie"]

    return RawTicket(
        ticket_id = str(ticket["id"]),
        # "2026-06-23 11:45:05" -> date(2026, 6, 23); pora dnia nigdy nie trafia do artefaktu.
        date      = Date.fromisoformat(ticket["created_at"][:SOURCE_DATETIME_LENGTH]),
        category  = ticket.get("kategoria") or "",
        subject   = strip_html(ticket.get("czego_dotyczy") or ""),
        body      = strip_html(ticket.get("szczegolowy_opis") or ""),
        # `or []` zamiast domyślnej wartości w `get()`: eksport zapisuje klucz z wartością null dla
        # zgłoszenia, którego nikt nie skomentował, a domyślna działa tylko przy BRAKU klucza.
        # Takich jest 29 z 1825 wyeksportowanych zgłoszeń — klasa „ani jednego komentarza
        # dostawcy", którą CLAUDE.md wymienia jako sygnał rekordu bez wiedzy.
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
