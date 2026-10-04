from datetime import date as Date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Ile wątków da się odczytać jednym wywołaniem. Wątki są długie — bywa po kilka tysięcy słów —
# więc model ma czytać te, które wybrał po kartach, a nie wszystko, co znalazł.
MAX_THREADS_PER_READ = 5

TicketId = Annotated[str, Field(min_length=1)]


class ReadTicketsThreadQuery(BaseModel):
    """
    Description:
    O co agent pyta `read_tickets_thread`: numery zgłoszeń z wyszukiwania, których oryginalny
    wątek chce przeczytać.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    ticket_ids: list[TicketId] = Field(
        min_length = 1,
        max_length = MAX_THREADS_PER_READ,
        examples   = [["90011"]],
    )


class TicketThread(BaseModel):
    """
    Description:
    Jeden odczytany wątek: numer zgłoszenia, data, temat i cały tekst wątku w oryginalnym
    brzmieniu, po anonimizacji — temat, opis zgłaszającego i komentarze.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id: str  = Field(min_length=1, examples=["90011"])
    date:      Date = Field(examples=["2026-03-02"])
    # Temat zgłoszenia — tytuł na liście źródeł.
    subject:   str  = Field(min_length=1, examples=["Błąd przy podpisie"])
    thread:    str  = Field(min_length=1, examples=["ZGŁOSZENIE 90011 z 2026-03-02\n…"])


class ReadTicketsThreadResult(BaseModel):
    """
    Description:
    Co dał jeden odczyt `read_tickets_thread`: wszystkie żądane wątki, w kolejności żądania.
    Wynik częściowy nie istnieje — brak któregokolwiek zgłoszenia to błąd (`UnknownTicketError`).
    """

    model_config = ConfigDict(extra="forbid")

    threads: list[TicketThread] = Field(default_factory=list)
