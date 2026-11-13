from pydantic import BaseModel, Field


class TicketImportFailure(BaseModel):
    """
    Description:
    Zgłoszenie, którego masowy import nie sparsował: numer i nazwa wyjątku, bez treści, bo przebieg
    operuje na danych klientów. Ponowne uruchomienie importu bierze je od nowa, bo karty nie ma.
    """

    ticket_id: str = Field(examples=["34071"])
    error:     str = Field(examples=["LLMError", "AnonymizationError"])
