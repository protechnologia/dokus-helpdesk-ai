from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent_tools.models import ExactText, MatchKind


class FindTicketsTextQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_tickets_text`: to, co w zgłoszeniu da się znaleźć słowo w słowo. Pola
    nazywają, czego agent szuka, a nie jak leży to w bazie — o podciągu i odmianie przez słownik
    rozstrzyga narzędzie.
    """

    # Nieznany argument to błąd, jak w `FindTicketsVectorQuery`.
    model_config = ConfigDict(extra="forbid")

    # Jedna fraza: kod błędu, sygnatura albo fragment komunikatu — przepisana bez zmian. Kilka
    # fraz to kilka wywołań: wynik mówi wtedy, która z nich trafiła.
    exact: ExactText | None = Field(default=None, examples=["SQLSTATE[23000]"])
    # Słowa kluczowe; odmiana nie ma znaczenia.
    words: str | None       = Field(default=None, min_length=1, examples=["załącznik limit"])

    @model_validator(mode="after")
    def _requires_something_to_search(self) -> "FindTicketsTextQuery":
        """
        Description:
        Odrzuca zapytanie bez ani jednego pola: puste wyszukiwanie zwróciłoby pustą listę, która
        wygląda jak „niczego takiego nie było".

        Example args:
            (brak)

        Example result:
            ten sam obiekt, gdy podano `exact` albo `words`

        Raises:
            ValueError: oba pola puste
        """
        if not self.exact and not self.words:
            raise ValueError("podaj co najmniej jedno z pól: exact, words")

        return self


class MatchedTicket(BaseModel):
    """
    Description:
    Jedno zgłoszenie zwrócone przez `find_tickets_text`: jego numer i to, czym je znaleziono.
    Treści tu nie ma — wątek daje `read_tickets_thread`, kartę `read_tickets_card`.

    Podobieństwa tu nie ma: dopasowanie dosłowne nie ma stopnia, a etykieta mówi więcej niż
    liczba — trafienie po przepisanym komunikacie waży inaczej niż po słowach kluczowych.
    Dopasowanego fragmentu też nie: treść daje wyłącznie odczyt, bo tylko on trafia na listę
    źródeł.
    """

    model_config = ConfigDict(extra="forbid")

    ticket_id:  str       = Field(min_length=1, examples=["90011"])
    matched_by: MatchKind = Field(examples=["exact"])


class FindTicketsTextResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_tickets_text`: numery znalezionych zgłoszeń i liczba
    pominiętych ponad limit. Licznik idzie razem z numerami, bo „trafień jest pięć" i „pokazano
    pięć z czterdziestu" to różne odpowiedzi — druga mówi agentowi, że zapytanie było zbyt ogólne.
    """

    model_config = ConfigDict(extra="forbid")

    tickets:            list[MatchedTicket] = Field(default_factory=list)
    omitted_over_limit: int                 = Field(default=0, ge=0, examples=[35])
