from pydantic import BaseModel, ConfigDict, Field

from app.model.ticket_parsed import ParsedTicket


class FindTicketsQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_tickets`: zgłoszenie opisane w kształcie korpusu — te same dwa pola,
    z których zbudowano wektory indeksu. Parsowanie zgłoszenia pod wyszukiwanie to zadanie agenta
    (jak to robić, mówi mu prompt), więc narzędzie nie woła parsera: składa z pól tekst do
    embeddingu tą samą funkcją co indeksacja (`build_embedding_text()`) i szuka.
    """

    # Nieznany argument (np. `limit`) to błąd — liczbę trafień i próg ustawia konfiguracja.
    model_config = ConfigDict(extra="forbid")

    problem:  str = Field(min_length=1, examples=["Wysyłka przez ePUAP kończy się błędem"])
    symptoms: str = Field(min_length=1, examples=["Po kliknięciu Wyślij komunikat o braku sieci"])


class FoundTicket(BaseModel):
    """
    Description:
    Jedno historyczne zgłoszenie zwrócone przez `find_tickets`: podobieństwo, z jakim je
    znaleziono, i sparsowane zgłoszenie z payloadu Qdranta.

    Całe `ParsedTicket`, a nie wybrany podzbiór pól: payload jest zapisywany z tego modelu
    (`TicketPoint.from_ticket`), a druga klasa wypisująca te same klucze byłaby drugim miejscem,
    w którym da się o jednym zapomnieć. Id i data należą do samego zgłoszenia — `cite()` czyta je
    stamtąd, a nie z kopii trzymanej obok.
    """

    model_config = ConfigDict(extra="forbid")

    score:  float = Field(examples=[0.87])
    ticket: ParsedTicket


class FindTicketsResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_tickets`: zgłoszenia, które przeszły `RAG_SCORE_MIN`, i liczba
    odciętych. Licznik idzie razem z elementami, bo „nic nie było" i „próg to wyciął" to różne
    odpowiedzi, a agent decydujący, czy ma dość materiału, musi je rozróżniać.
    """

    model_config = ConfigDict(extra="forbid")

    items:                   list[FoundTicket] = Field(default_factory=list)
    dropped_below_threshold: int               = Field(default=0, ge=0, examples=[3])
