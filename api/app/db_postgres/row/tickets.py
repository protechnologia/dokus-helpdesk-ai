from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field

from app.model.ticket_raw import RawTicket


class TicketRow(BaseModel):
    """
    Description:
    Jeden wiersz tabeli zgłoszeń — pole na każdą kolumnę, w tych samych typach co w bazie.

    Do czego:
    Tabela trzyma zgłoszenie w oryginalnym brzmieniu, po anonimizacji: cały wątek jako jeden
    tekst. Karty zgłoszenia tu nie ma — karty trzyma baza wektorowa.

    Flow:
        1. Indeksacja buduje wiersz przez `from_thread()`: numer, data i wątek PO ANONIMIZACJI.
        2. Tabela zapisuje pola wprost do kolumn o tych samych nazwach.
        3. Szukanie i odczyt oddają takie same wiersze.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id:   str  = Field(min_length=1, examples=["33644"])
    ticket_date: Date = Field(examples=["2026-03-14"])
    # Temat wycięty z wątku — tytuł, po którym człowiek rozpozna zgłoszenie na liście źródeł.
    subject:     str  = Field(min_length=1, examples=["Błąd wysyłki przez ePUAP"])
    # Pełny tekst wątku po anonimizacji: temat, opis zgłaszającego i komentarze.
    thread:      str  = Field(min_length=1, examples=["ZGŁOSZENIE 33644 z 2026-03-14\nTemat: …"])

    @classmethod
    def from_thread(
        cls,
        ticket_id:   str,   # np. "33644"
        ticket_date: Date,  # np. date(2026, 3, 14)
        thread:      str,   # pełny tekst wątku po anonimizacji, w kształcie `RawTicket.as_thread()`
    ) -> "TicketRow":
        """
        Description:
        Buduje wiersz z numeru, daty i tekstu wątku. Temat wycina z wątku, a nie bierze ze źródła:
        do bazy trafia wyłącznie tekst po anonimizacji, a anonimizowany jest cały wątek naraz.

        Example args:
            ticket_id="33644"
            ticket_date=date(2026, 3, 14)
            thread="ZGŁOSZENIE 33644 z 2026-03-14\\nTemat: Błąd wysyłki przez ePUAP\\n\\nOPIS…"

        Example result:
            TicketRow(ticket_id="33644", subject="Błąd wysyłki przez ePUAP", thread="ZGŁOSZENIE…")

        Raises:
            ValueError: w wątku nie ma linii z tematem
        """
        row = cls(
            ticket_id   = ticket_id,
            ticket_date = ticket_date,
            subject     = RawTicket.subject_of_thread(thread),
            thread      = thread,
        )

        return row
