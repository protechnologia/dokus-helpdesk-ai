from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.model.ticket_parsed import ParsedTicket

# Dosłowny ciąg ma co najmniej trzy znaki: krótszy trafia w przypadkowe miejsca (numer telefonu,
# data), a zgłoszenie znalezione po „50" wygląda na trafienie, choć nim nie jest.
ExactText = Annotated[str, Field(min_length=3)]

# Czym zgłoszenie znaleziono: dosłownym ciągiem albo słowami kluczowymi.
MatchKind = Literal["exact", "words"]


class FindTicketsTextQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_tickets_text`: to, co w zgłoszeniu da się znaleźć słowo w słowo. Pola
    nazywają, czego agent szuka, a nie jak leży to w bazie — o podciągu i odmianie przez słownik
    rozstrzyga narzędzie.
    """

    # Nieznany argument to błąd, jak w `FindTicketsVectorQuery`.
    model_config = ConfigDict(extra="forbid")

    # Kody błędów, sygnatury i fragmenty komunikatów — przepisane bez zmian.
    exact: list[ExactText] = Field(default_factory=list, examples=[["SQLSTATE[23000]"]])
    # Słowa kluczowe; odmiana nie ma znaczenia.
    words: str | None      = Field(default=None, min_length=1, examples=["załącznik limit"])

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
    Jedno historyczne zgłoszenie zwrócone przez `find_tickets_text`: czym je znaleziono i całe
    sparsowane zgłoszenie — to samo, które oddaje `find_tickets_vector`.

    Podobieństwa tu nie ma: dopasowanie dosłowne nie ma stopnia, a etykieta mówi więcej niż
    liczba — trafienie po przepisanym komunikacie waży inaczej niż po słowach kluczowych.
    """

    model_config = ConfigDict(extra="forbid")

    matched_by: MatchKind = Field(examples=["exact"])
    ticket:     ParsedTicket


class FindTicketsTextResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_tickets_text`: znalezione zgłoszenia i liczba pominiętych
    ponad limit. Licznik idzie razem z elementami, bo „trafień jest pięć" i „pokazano pięć
    z czterdziestu" to różne odpowiedzi — druga mówi agentowi, że zapytanie było zbyt ogólne.
    """

    model_config = ConfigDict(extra="forbid")

    items:              list[MatchedTicket] = Field(default_factory=list)
    omitted_over_limit: int                 = Field(default=0, ge=0, examples=[35])
