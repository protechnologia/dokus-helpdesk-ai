from datetime import date as Date

from pydantic import BaseModel, Field

from app.entry_routers.models import LogItem, UsageItem


class TicketCard(BaseModel):
    """
    Description:
    Odpowiedź `POST /parse-ticket`: karta zgłoszenia, czyli sparsowane pola w kształcie korpusu.
    Własny model, a nie `ParsedTicket` przepuszczony wprost — model domenowy nie wychodzi przez
    HTTP.

    Niesie tekst klienta (nazwiska bywają w `problem`), co jest dopuszczalne, bo wołającym jest
    helpdesk, do którego zgłoszenie należy — i jest powodem, by endpoint stał za uwierzytelnianiem
    (p. 36).
    """

    ticket_id:         str       = Field(examples=["41002"])
    date:              Date      = Field(examples=["2026-08-19"])
    component:         str       = Field(examples=["ePUAP"])
    problem:           str       = Field(examples=["Wysyłka kończy się błędem"])
    symptoms:          str       = Field(examples=["Komunikat o braku sieci"])
    error_codes:       list[str] = Field(default_factory=list, examples=[["ERR-4210"]])
    cause:             str       = Field(examples=["brak"])
    excluded_causes:   list[str] = Field(examples=[["Brak miejsca na dysku"]])
    solution:          str       = Field(examples=["brak"])
    resolution:        str       = Field(examples=["naprawione"])
    questions_summary: str       = Field(examples=["brak"])
    useful:            bool      = Field(examples=[True])
    useful_reason:     str       = Field(examples=["Wątek podaje przyczynę i rozwiązanie."])
    usage:             UsageItem
    log:               list[LogItem] = Field(default_factory=list)
