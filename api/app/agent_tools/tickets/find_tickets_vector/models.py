from pydantic import BaseModel, ConfigDict, Field


class FindTicketsVectorQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_tickets_vector`: zgłoszenie opisane w kształcie korpusu — te same dwa
    pola, z których zbudowano wektory indeksu. Parsowanie zgłoszenia pod wyszukiwanie to zadanie
    agenta (jak to robić, mówi mu prompt), więc narzędzie nie woła parsera: składa z pól tekst do
    embeddingu tą samą funkcją co indeksacja (`build_embedding_text()`) i szuka.
    """

    # Nieznany argument (np. `limit`) to błąd — liczbę trafień i próg ustawia konfiguracja.
    model_config = ConfigDict(extra="forbid")

    problem:  str = Field(min_length=1, examples=["Wysyłka przez ePUAP kończy się błędem"])
    symptoms: str = Field(min_length=1, examples=["Po kliknięciu Wyślij komunikat o braku sieci"])


class FoundTicket(BaseModel):
    """
    Description:
    Jedno zgłoszenie zwrócone przez `find_tickets_vector`: jego numer i podobieństwo, z jakim je
    znaleziono. Treści tu nie ma — kartę daje `read_tickets_card`, wątek `read_tickets_thread`.

    Sam numer, bez `problem` karty: te same objawy mają w tym korpusie różne przyczyny, a wiersz
    z samym objawem zachęcałby do przeczytania jednej karty zamiast wszystkich.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id: str   = Field(min_length=1, examples=["33644"])
    score:     float = Field(examples=[0.87])


class FindTicketsVectorResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_tickets_vector`: numery zgłoszeń, które przeszły
    `RAG_SCORE_MIN`, od najbardziej podobnego, i liczba odciętych. Licznik idzie razem z numerami,
    bo „nic nie było" i „próg to wyciął" to różne odpowiedzi, a agent decydujący, czy szukać
    dalej, musi je rozróżniać.
    """

    model_config = ConfigDict(extra="forbid")

    tickets:                 list[FoundTicket] = Field(default_factory=list)
    dropped_below_threshold: int               = Field(default=0, ge=0, examples=[3])
