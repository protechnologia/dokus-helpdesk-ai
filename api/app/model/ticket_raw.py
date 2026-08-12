from datetime import date as Date

from pydantic import BaseModel, Field

from app.model.ticket_raw_comment import RawComment


class RawTicket(BaseModel):
    """
    Description:
    One source ticket, normalised. This is the only shape the rest of the system sees — column
    names, HTML and the file layout stay behind an adapter in `ingest/` (CLAUDE.md -> "Dane
    wejściowe").

    Do czego:
    Lives in `model/`, not next to the reader that fills it, because it is the INPUT half of the
    contract whose output half is `ParsedTicket`: one reader per source format fills it, and every
    one of them must agree on the same shape. Keeping it next to `ticket_parsed.py` makes the two
    sides of that transformation readable together.

    Flow:
        1. An adapter (today `parser_ticket_raw.load_raw_ticket()`, in stage 10 a SQL one) reads
           one source record and fills this model, stripping HTML on the way in.
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
