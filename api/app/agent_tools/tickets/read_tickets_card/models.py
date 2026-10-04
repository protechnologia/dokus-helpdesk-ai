from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.core_model.ticket_parsed import ParsedTicket

# Ile kart da się odczytać jednym wywołaniem. Karty są krótkie, a model ma przeczytać wszystkie
# znalezione — także z kilku wyszukań naraz — więc limit jest wyższy niż przy wątkach.
MAX_CARDS_PER_READ = 20

TicketId = Annotated[str, Field(min_length=1)]


class ReadTicketsCardQuery(BaseModel):
    """
    Description:
    O co agent pyta `read_tickets_card`: numery zgłoszeń z wyszukiwania, których karty chce
    przeczytać.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    ticket_ids: list[TicketId] = Field(
        min_length = 1,
        max_length = MAX_CARDS_PER_READ,
        examples   = [["90001", "90002"]],
    )


class ReadTicketsCardResult(BaseModel):
    """
    Description:
    Co dał jeden odczyt `read_tickets_card`: karty zgłoszeń w kolejności żądania i numery, dla
    których karty nie ma.

    Brak karty to stan poprawny, nie błąd: wątek ma każde zgłoszenie, kartę tylko to, które
    przeszło parsowanie i filtr jakości. Numer bez karty wraca osobno, żeby model sięgnął po
    wątek, a pozostałe karty dostał normalnie.
    """

    model_config = ConfigDict(extra="forbid")

    cards:        list[ParsedTicket] = Field(default_factory=list)
    without_card: list[str]          = Field(default_factory=list, examples=[["90011"]])
