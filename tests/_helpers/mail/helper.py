"""
Description:
Słownik maili zmyślony i zgłoszenia z kanału „Automat mailowy” do testów normalizera maili,
jego loadera i skryptu słownika.

| funkcja                   | do czego                                                          |
|---------------------------|-------------------------------------------------------------------|
| `safe_templates()`        | słownik szablonów zmyślony, z `data/safe/mail/slownik.json`       |
| `safe_vendor_names()`     | nazwy dostawcy zmyślone, z `data/safe/mail/nazwy.json`            |
| `safe_mail_ticket()`      | zmyślony wątek kanału z `data/safe/mail/raw-db/`, z którego       |
|                           | powstał słownik                                                   |
| `safe_mail_request()`     | ten sam wątek jako żądanie do tras grafów (`TicketRequest`)       |
| `copy_safe_mail_export()` | ten sam wątek jako plik eksportu w `raw-db/` korpusu testu        |
| `mail_ticket()`           | zgłoszenie kanału z podanym opisem i komentarzami, bez dysku      |
"""

import shutil
from collections.abc import Sequence
from datetime import date as Date
from pathlib import Path
from typing import Any

from app.core_model.dicts.mail_templates import MailTemplates
from app.core_model.dicts.vendor_names import VendorNames
from app.core_model.tickets.raw_comment import RawComment
from app.core_model.tickets.raw_ticket import RawTicket
from app.core_model.tickets.tickets_corpus import TicketsCorpus
from app.core_service.loader_mail_dictionary import load_mail_templates, load_vendor_names
from app.core_service.parser_ticket_raw import MAIL_CATEGORY, load_raw_ticket
from tests._helpers.mail.constants import SAFE_MAIL_DIR


def safe_templates() -> MailTemplates:
    """
    Description:
    Czyta słownik szablonów zmyślony: skróty fragmentów wspólnych zmyślonym wątkom
    z `data/safe/mail/raw-db/`, wśród nich stopki dostawcy.

    Example args:
        (brak)

    Example result:
        MailTemplates(threads=3, run_words=12, min_threads=2, digests=["0a1b…", …], …)
    """
    return load_mail_templates(SAFE_MAIL_DIR)


def safe_vendor_names() -> VendorNames:
    """
    Description:
    Czyta nazwy dostawcy zmyślone: „Przykładsoft Sp. z o.o.”.

    Example args:
        (brak)

    Example result:
        VendorNames(names=["Przykładsoft Sp. z o.o."])
    """
    return load_vendor_names(SAFE_MAIL_DIR)


def safe_mail_ticket(ticket_id: int) -> RawTicket:   # np. 41101
    """
    Description:
    Czyta jeden zmyślony wątek kanału z `data/safe/mail/raw-db/`, czytnikiem eksportu, tak jak
    czyta je skrypt słownika.

    Example args:
        ticket_id=41101

    Example result:
        RawTicket(ticket_id="41101", category="Automat mailowy", subject="Błąd wysyłki", …)
    """
    corpus = TicketsCorpus(root=SAFE_MAIL_DIR)

    return load_raw_ticket(corpus.raw_db_dir / f"zgloszenie-{ticket_id}.json")


def mail_ticket(
    body:     str,                             # np. "Dzień dobry,\nod wczoraj nie możemy…"
    comments: Sequence[tuple[str, str]] = (),  # np. [("klient", "Proszę odnowić…")]: rola, treść
    category: str = MAIL_CATEGORY,             # np. "Błąd" — zgłoszenie spoza kanału
) -> RawTicket:
    """
    Description:
    Składa zgłoszenie z podanym opisem i komentarzami, w kanale „Automat mailowy”, chyba że
    podano inny. Komentarze dostają kolejne godziny z jednego dnia.

    Example args:
        body="Dzień dobry,\\nod wczoraj nie możemy wysłać pisma."
        comments=[("klient", "Proszę odnowić uprawnienie.")]
        category="Automat mailowy"

    Example result:
        RawTicket(ticket_id="41200", category="Automat mailowy", body="Dzień dobry,…", …)
    """
    raw_comments = [
        RawComment(kind="zwyczajny", role=role, created_at=f"2026-07-03 {hour}:00:00", body=text)
        for hour, (role, text) in enumerate(comments, start=10)
    ]
    ticket = RawTicket(
        ticket_id = "41200",
        date      = Date(2026, 7, 3),
        category  = category,
        subject   = "Błąd wysyłki",
        body      = body,
        comments  = raw_comments,
    )

    return ticket


def safe_mail_request(ticket_id: int) -> dict[str, Any]:   # np. 41101
    """
    Description:
    Składa żądanie do tras grafów (`TicketRequest` jako JSON) ze zmyślonego wątku kanału
    z `data/safe/mail/raw-db/`: numer, data, temat, kategoria, surowy opis i komentarze z rolami
    z bazy, tak jak przysłałby je helpdesk.

    Example args:
        ticket_id=41101

    Example result:
        {"ticket_id": "41101", "category": "Automat mailowy", "body": "Dzień dobry,…", …}
    """
    raw     = safe_mail_ticket(ticket_id)
    request = {
        "ticket_id": raw.ticket_id,
        "date":      raw.date.isoformat(),
        "subject":   raw.subject,
        "category":  raw.category,
        "body":      raw.body,
        "comments":  [
            {"body": comment.body, "role": comment.role, "created_at": comment.created_at}
            for comment in raw.comments
        ],
    }

    return request


def copy_safe_mail_export(
    root:      Path,  # np. tmp_path — katalog korpusu testu
    ticket_id: int,   # np. 41101
) -> Path:
    """
    Description:
    Kopiuje plik eksportu zmyślonego wątku kanału z `data/safe/mail/raw-db/` do `raw-db/` korpusu
    testu, pod tą samą nazwą: zgłoszenie zamknięte, z kategorii „Automat mailowy”.

    Example args:
        root=Path("/tmp/pytest-0/korpus")
        ticket_id=41101

    Example result:
        Path("/tmp/pytest-0/korpus/raw-db/zgloszenie-41101.json")
    """
    name   = f"zgloszenie-{ticket_id}.json"
    target = TicketsCorpus(root=root).raw_db_dir / name

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TicketsCorpus(root=SAFE_MAIL_DIR).raw_db_dir / name, target)

    return target
