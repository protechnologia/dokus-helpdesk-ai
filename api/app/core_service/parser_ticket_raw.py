"""
Description:
Czytnik plików eksportu z `data/unsafe/raw/` (wytwarza je `scripts/export_raw_tickets.py`). Z
jednego pliku JSON robi znormalizowany `RawTicket` — jedyny kształt zgłoszenia źródłowego, jaki
widzi reszta systemu. Jeden czytnik na format źródła: przy masowym imporcie (p. 31) dojdzie obok
wariant SQL.

Przed — plik `data/unsafe/raw/zgloszenie-33644.json`:

    {
      "zrodlo": "mysql_helpdesk_20260724-141140.sql",
      "zgloszenie": {
        "id":               33644,
        "created_at":       "2026-06-23 11:45:05",
        "kategoria":        "Błąd",
        "czego_dotyczy":    "Błąd wysyłki",
        "szczegolowy_opis": "<p>Dzień dobry,</p><p>nie działa wysyłka &quot;ePUAP&quot;.</p>",
        "status":           "rozwiazany",
        "instytucja":       "Urząd Gminy X",
        …
      },
      "komentarze": [
        {
          "id":         34485,
          "typ":        "rozwiazanie",
          "autor_rola": "konsultant",
          "created_at": "2026-06-23 12:01:21",
          "tresc":      "<p>Odblokowano kolejkę wysyłki.<br>Proszę ponowić.</p>"
        }
      ]
    }

Po — wynik `load_raw_ticket()`:

    RawTicket(
        ticket_id = "33644",
        date      = date(2026, 6, 23),
        category  = "Błąd",
        subject   = "Błąd wysyłki",
        body      = 'Dzień dobry,\\nnie działa wysyłka "ePUAP".',
        comments  = [
            RawComment(
                kind       = "rozwiazanie",
                role       = "konsultant",
                created_at = "2026-06-23 12:01:21",
                body       = "Odblokowano kolejkę wysyłki.\\nProszę ponowić.",
            ),
        ],
    )

Co się zmieniło:

1. Z tematu, opisu i każdego komentarza znika HTML (`strip_html`): tagi akapitów i `<br>` stają
   się nową linią, encje (`&quot;`) zwykłymi znakami.
2. `id` staje się napisem, a `created_at` zgłoszenia samą datą, bez godziny.
3. Nazwy kolumn bazy przechodzą na pola modelu (`szczegolowy_opis` → `body`, `typ` → `kind`).
4. Reszta kolumn zostaje w pliku: status, instytucja, dane kontaktowe i pozostałe metadane.
"""

import json
from datetime import date as Date
from pathlib import Path

from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_util.html import strip_html

# Znaczniki czasu w źródle to datetime z MySQL; do artefaktu trafia tylko część z datą.
SOURCE_DATETIME_LENGTH = len("2026-06-23")


def load_raw_ticket(path: Path) -> RawTicket:   # np. Path("data/unsafe/raw/zgloszenie-33644.json")
    """
    Description:
    Czyta jeden plik eksportu z `data/unsafe/raw/` i go normalizuje. Każde pole HTML jest
    strippowane tutaj, więc nic dalej nie musi wiedzieć, że źródło trzyma znaczniki.

    Example args:
        path=Path("data/unsafe/raw/zgloszenie-33644.json")

    Example result:
        RawTicket(ticket_id="33644", date=date(2026, 6, 23), subject="Błąd wysyłki", …)

    Raises:
        KeyError: plik nie ma kształtu, który wytwarza scripts/export_raw_tickets.py
        ValueError: plik nie jest poprawnym JSON-em albo znacznik czasu nie daje się odczytać
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    ticket  = payload["zgloszenie"]

    raw_ticket = RawTicket(
        ticket_id = str(ticket["id"]),
        # "2026-06-23 11:45:05" -> date(2026, 6, 23); pora dnia nigdy nie trafia do artefaktu.
        date      = Date.fromisoformat(ticket["created_at"][:SOURCE_DATETIME_LENGTH]),
        category  = ticket.get("kategoria") or "",
        subject   = strip_html(ticket.get("czego_dotyczy") or ""),
        body      = strip_html(ticket.get("szczegolowy_opis") or ""),
        # Zgłoszenie bez komentarzy ma w eksporcie `"komentarze": null` (29 z 1825), a wtedy
        # `get("komentarze", [])` oddaje None, nie [] — stąd `or []`.
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

    return raw_ticket
