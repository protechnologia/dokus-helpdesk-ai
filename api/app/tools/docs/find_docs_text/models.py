from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.model.doc_section import DocSection

# Dosłowny ciąg ma co najmniej trzy znaki — krótszy trafia w przypadkowe miejsca.
ExactText = Annotated[str, Field(min_length=3)]

# Czym sekcję znaleziono.
MatchKind = Literal["exact", "words"]


class FindDocsTextQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_docs_text`: to, co w dokumentacji da się znaleźć słowo w słowo. Pola
    nazywają, czego agent szuka, a nie jak leży to w bazie — o podciągu i odmianie przez słownik
    rozstrzyga narzędzie.
    """

    # Nieznany argument to błąd, jak w `FindTicketsVectorQuery`.
    model_config = ConfigDict(extra="forbid")

    # Nazwy opcji, komunikaty i kody — przepisane bez zmian.
    exact: list[ExactText] = Field(default_factory=list, examples=[["Uprawnienia → Kancelaria"]])
    # Słowa kluczowe; odmiana nie ma znaczenia.
    words: str | None      = Field(default=None, min_length=1, examples=["uprawnienie kancelaria"])

    @model_validator(mode="after")
    def _requires_something_to_search(self) -> "FindDocsTextQuery":
        """
        Description:
        Odrzuca zapytanie bez ani jednego pola: puste wyszukiwanie zwróciłoby pustą listę, która
        wygląda jak „dokumentacja o tym milczy".

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


class MatchedSection(BaseModel):
    """
    Description:
    Jedna sekcja dokumentacji zwrócona przez `find_docs_text`: czym ją znaleziono, zdanie,
    w którym padło dopasowanie, i opis sekcji z metryczki.

    Fragment (`snippet`) pozwala agentowi zdecydować o odczycie bez czytania całej sekcji. Nie
    zastępuje odczytu: źródłem odpowiedzi jest dopiero sekcja z `read_docs`.
    """

    model_config = ConfigDict(extra="forbid")

    matched_by: MatchKind = Field(examples=["exact"])
    snippet:    str       = Field(min_length=1, examples=["…w Ustawienia → Uprawnienia…"])
    section:    DocSection


class FindDocsTextResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_docs_text`: znalezione sekcje i liczba pominiętych ponad
    limit — liczona z tego samego powodu co w `FindTicketsTextResult`.
    """

    model_config = ConfigDict(extra="forbid")

    items:              list[MatchedSection] = Field(default_factory=list)
    omitted_over_limit: int                  = Field(default=0, ge=0, examples=[12])
