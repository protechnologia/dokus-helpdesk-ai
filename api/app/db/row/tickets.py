from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field

from app.model.ticket_parsed import ParsedTicket

# Kody błędów w kolumnie tekstowej: jeden kod na linię.
CODES_SEPARATOR = "\n"


class TicketRow(BaseModel):
    """
    Description:
    Jeden wiersz tabeli zgłoszeń — pole na każdą kolumnę, w tych samych typach co w bazie.

    Do czego:
    W tym kształcie wiersz wchodzi do tabeli i z niej wraca. Na sparsowane zgłoszenie i z niego
    przechodzi się jawnie: `from_ticket()` przy zapisie, `to_ticket()` po odczycie.

    Flow:
        1. Indeksacja buduje wiersz z `ParsedTicket` i pełnego tekstu wątku PO ANONIMIZACJI.
        2. Tabela zapisuje pola wprost do kolumn o tych samych nazwach.
        3. Szukanie i odczyt oddają takie same wiersze; narzędzie bierze z nich `to_ticket()`
           albo `thread`.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id:                     str  = Field(min_length=1, examples=["33644"])
    ticket_date:                   Date = Field(examples=["2026-03-14"])
    component:                     str  = Field(examples=["ePUAP"])
    problem:                       str  = Field(examples=["Wysyłka przez ePUAP kończy się błędem"])
    symptoms:                      str  = Field(examples=["Po kliknięciu Wyślij komunikat o sieci"])
    # Kody błędów, każdy w swojej linii; pusty tekst to brak kodów.
    error_codes:                   str  = Field(examples=["ERR-4210\nSQLSTATE 23000"])
    cause:                         str  = Field(examples=["Certyfikat bez uprawnienia"])
    solution:                      str  = Field(examples=["Wygenerowano nowy certyfikat."])
    resolution:                    str  = Field(examples=["naprawione"])
    resolution_vocabulary_version: int  = Field(examples=[1])
    questions_summary:             str  = Field(examples=["pytano o wersję przeglądarki"])
    # Pełny tekst wątku po anonimizacji: opis zgłaszającego i komentarze.
    thread:                        str  = Field(min_length=1, examples=["Dzień dobry, przy…"])

    @classmethod
    def from_ticket(
        cls,
        ticket: ParsedTicket,  # np. ParsedTicket(ticket_id="33644", …)
        thread: str,           # pełny tekst wątku po anonimizacji
    ) -> "TicketRow":
        """
        Description:
        Buduje wiersz ze sparsowanego zgłoszenia i tekstu wątku. Lista kodów błędów staje się
        jednym tekstem, po kodzie na linię.

        Example args:
            ticket=ParsedTicket(ticket_id="33644", error_codes=["ERR-4210"], …)
            thread="Dzień dobry, przy wysyłce przez ePUAP…"

        Example result:
            TicketRow(ticket_id="33644", error_codes="ERR-4210", thread="Dzień dobry…", …)
        """
        row = cls(
            ticket_id                     = ticket.ticket_id,
            ticket_date                   = ticket.date,
            component                     = ticket.component,
            problem                       = ticket.problem,
            symptoms                      = ticket.symptoms,
            error_codes                   = CODES_SEPARATOR.join(ticket.error_codes),
            cause                         = ticket.cause,
            solution                      = ticket.solution,
            resolution                    = ticket.resolution,
            resolution_vocabulary_version = ticket.resolution_vocabulary_version,
            questions_summary             = ticket.questions_summary,
            thread                        = thread,
        )

        return row

    def to_ticket(self) -> ParsedTicket:
        """
        Description:
        Odtwarza sparsowane zgłoszenie z pól wiersza — to, które narzędzie pokazuje modelowi.

        Example args:
            (brak)

        Example result:
            ParsedTicket(ticket_id="33644", error_codes=["ERR-4210"], …)
        """
        # Pusty tekst to brak kodów — `"".split()` dałoby jeden pusty kod.
        codes = self.error_codes.split(CODES_SEPARATOR) if self.error_codes else []

        ticket = ParsedTicket(
            ticket_id                     = self.ticket_id,
            date                          = self.ticket_date,
            component                     = self.component,
            problem                       = self.problem,
            symptoms                      = self.symptoms,
            error_codes                   = codes,
            cause                         = self.cause,
            solution                      = self.solution,
            resolution                    = self.resolution,
            resolution_vocabulary_version = self.resolution_vocabulary_version,
            questions_summary             = self.questions_summary,
        )

        return ticket
