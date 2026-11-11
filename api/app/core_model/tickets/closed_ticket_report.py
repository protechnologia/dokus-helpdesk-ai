from pydantic import BaseModel, Field

from app.core_model.tickets.quality_verdict import RuleHit


class ClosedTicketReport(BaseModel):
    """
    Description:
    Co stało się z jednym zamkniętym zgłoszeniem, które trafiło do korpusu (p. 30): czy zastąpiło
    wcześniejszą kartę, czy jego karta jest w indeksie, a jeśli nie, to które reguły filtra jakości
    ją odrzuciły. Oddaje go `ClosedTicketIndexer.add()`, a czyta trasa zamknięcia zgłoszenia.
    """

    ticket_id:  str           = Field(examples=["41002"])
    # Karta tego zgłoszenia leżała już w korpusie — zgłoszenie zamknięto ponownie.
    replaced:   bool          = Field(examples=[False])
    # Karta przeszła filtr jakości, więc jest w Qdrancie, a jej wątek w tabeli wątków.
    indexed:    bool          = Field(examples=[True])
    # Reguły, które kartę odrzuciły; puste, gdy karta jest w indeksie.
    dropped_by: list[RuleHit] = Field(default_factory=list)
