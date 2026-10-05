from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class ReadTicketsThreadQuery(BaseModel):
    """
    Description:
    O co agent pyta `read_tickets_thread`: numer jednego zgłoszenia z wyszukiwania, którego
    oryginalny wątek chce przeczytać.

    Jeden numer na wywołanie, nie lista: wątki są długie — bywa po kilka tysięcy słów — a tak
    limit wywołań narzędzia jest wprost limitem wątków przeczytanych w jednej sprawie. Przy liście
    model brał wszystkie znalezione numery naraz, a limit wywołań mnożył się przez jej długość.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    ticket_id: str = Field(min_length=1, examples=["90011"])


class TicketThread(BaseModel):
    """
    Description:
    Co daje jeden odczyt `read_tickets_thread`: numer zgłoszenia, data, temat i cały tekst wątku
    w oryginalnym brzmieniu, po anonimizacji — temat, opis zgłaszającego i komentarze.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id: str  = Field(min_length=1, examples=["90011"])
    date:      Date = Field(examples=["2026-03-02"])
    # Temat zgłoszenia — tytuł na liście źródeł.
    subject:   str  = Field(min_length=1, examples=["Błąd przy podpisie"])
    thread:    str  = Field(min_length=1, examples=["ZGŁOSZENIE 90011 z 2026-03-02\n…"])
