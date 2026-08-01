import html
import json
import re
from datetime import date as Date
from pathlib import Path

from pydantic import BaseModel, Field

# Source timestamps are MySQL datetimes; only the date half reaches the artifact.
SOURCE_DATETIME_LENGTH = len("2026-06-23")

# Block-level tags become a line break so paragraphs do not run together once the tags are gone;
# a naive strip would turn "<p>Krok 1</p><p>Krok 2</p>" into "Krok 1Krok 2".
_BLOCK_TAG   = re.compile(r"</(?:p|div|li|tr|h[1-6])>|<br\s*/?>", re.IGNORECASE)
_ANY_TAG     = re.compile(r"<[^>]+>")
_BLANK_LINES = re.compile(r"\n{3,}")


def strip_html(raw: str) -> str:   # e.g. "<p>Dzień dobry,</p><p>Nie działa&#039;</p>"
    """
    Description:
    Turns one HTML field of the source database into plain text. Runs before anything else reads
    the content: tags and entities in the prompt cost tokens, split words the model needs whole,
    and would land verbatim in the artifact (CLAUDE.md -> "Pułapki tej bazy").

    Order matters — entities are unescaped LAST. Doing it first would turn a `&lt;p&gt;` written by
    a user into a real tag, which the tag pass would then delete along with the text around it.

    Example args:
        raw="<p>Dzień dobry,</p><p>Nie działa wysyłka&#039;</p>"

    Example result:
        "Dzień dobry,\\nNie działa wysyłka'"
    """
    with_breaks  = _BLOCK_TAG.sub("\n", raw)
    without_tags = _ANY_TAG.sub("", with_breaks)
    unescaped    = html.unescape(without_tags)

    # Collapse the runs of blank lines the tag removal leaves behind.
    lines = [line.strip() for line in unescaped.splitlines()]

    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class RawComment(BaseModel):
    """
    Description:
    One comment of a source thread, already stripped of HTML. `kind` and `role` are carried into
    the prompt as CONTEXT, never as a verdict: the prompt itself tells the model not to trust
    them, because in this corpus a comment typed `rozwiazanie` is sometimes a question and the
    real resolution sometimes sits in an unlabelled one (CLAUDE.md -> "Pułapki tej bazy").
    """

    kind:       str = Field(examples=["rozwiazanie", "zwyczajny"])
    role:       str = Field(examples=["konsultant", "klient"])
    created_at: str = Field(examples=["2026-06-23 12:01:21"])
    body:       str = Field(examples=["Wygenerowano certyfikat z właściwym uprawnieniem."])


class RawTicket(BaseModel):
    """
    Description:
    One source ticket, normalised. This is the only shape the rest of the system sees — column
    names, HTML and the thread-assembly rules stay behind the adapter (CLAUDE.md -> "Dane
    wejściowe").

    Flow:
        1. `load_raw_ticket()` reads one export file and fills this model.
        2. `as_thread()` renders it as the text handed to the parsing prompt.
        3. `ticket_id` and `date` travel straight into `ParsedTicket` — they come from the source,
           never from the model, so there is nothing for an LLM to get wrong about them.
    """

    ticket_id: str  = Field(examples=["33644"])
    date:      Date = Field(examples=["2026-06-23"])
    # Read from the source but deliberately NOT mapped onto an artifact field: `category` was
    # dropped from the schema. It survives here because "Automat mailowy" marks the records whose
    # quoted mail history needs cleaning before parsing (CLAUDE.md -> "Mapowanie tabel").
    category:  str  = Field(examples=["Automat mailowy", "Błąd"])
    subject:   str  = Field(examples=["ESOD Dokus - Zakończona aktualizacja środowiska testowego"])
    body:      str  = Field(examples=["Dzień dobry, po aktualizacji nie działa wysyłka…"])

    comments: list[RawComment] = Field(default_factory=list)

    def as_thread(self) -> str:
        """
        Description:
        Renders the ticket as the text the parsing prompt receives. Comments keep their source
        order because this corpus rewards reading a thread as a chronology — the most valuable
        sentence is often in the last comment, sometimes written after the ticket was closed.

        Author and comment type are labelled but not acted upon: the prompt tells the model to
        weigh content over labels, so hiding them would remove context, while trusting them would
        reproduce a documented defect of this database.

        Example args:
            (none)

        Example result:
            "ZGŁOSZENIE 33644 z 2026-06-23\\nTemat: Błąd wysyłki\\n\\nOPIS ZGŁASZAJĄCEGO:\\n…"
        """
        parts = [
            f"ZGŁOSZENIE {self.ticket_id} z {self.date.isoformat()}",
            f"Temat: {self.subject}",
            "",
            "OPIS ZGŁASZAJĄCEGO:",
            self.body or "(brak opisu)",
        ]

        # Said out loud rather than left as silence: a thread with no comment at all is a known
        # class of unusable record, and the model should see that it is looking at one.
        if not self.comments:
            parts += ["", "(brak komentarzy w wątku)"]

        for index, comment in enumerate(self.comments, start=1):
            parts += [
                "",
                f"KOMENTARZ {index} — {comment.role}, {comment.created_at} (typ: {comment.kind}):",
                comment.body or "(pusty komentarz)",
            ]

        return "\n".join(parts)


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
