from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class FindDocsQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_docs`: zagadnienie albo słowa kluczowe funkcji czy procedury, której
    wyjaśnienia potrzebuje. Dopasowywane znaczeniowo do fragmentów dokumentacji.
    """

    # Nieznany argument to błąd, jak w FindTicketsQuery.
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["uprawnienia kancelaria e-Doręczenia"])


class FoundDoc(BaseModel):
    """
    Description:
    Jeden fragment dokumentacji produktu zwrócony przez `find_docs`.

    Kształt TYMCZASOWY: czy dokumentacja istnieje i w jakiej formie, jest wciąż otwarte
    (CLAUDE.md -> „Plan i TODO", p. 12), więc są tu tylko pola, których plan już wymaga — który
    fragment (to cytuje odpowiedź), który dokument, które wydanie opisuje, treść — do przejrzenia
    przy wczytaniu kolekcji (p. 20). Wydanie jest wymagane, nie opcjonalne: instrukcja do starszej
    wersji wprowadza w błąd dokładnie tak jak odmowa obalona później nowszym zgłoszeniem.
    """

    model_config = ConfigDict(extra="forbid")

    fragment_id: str         = Field(min_length=1, examples=["doc-7"])
    score:       float       = Field(examples=[0.62])
    document:    str         = Field(min_length=1, examples=["Instrukcja administratora"])
    version:     str         = Field(min_length=1, examples=["4.12"])
    date:        Date | None = Field(default=None, examples=["2026-05-04"])
    text:        str         = Field(min_length=1, examples=["Aby nadać uprawnienie, otwórz…"])


class FindDocsResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_docs`: fragmenty, które przeszły próg, i liczba odciętych —
    liczona z tego samego powodu co w `FindTicketsResult`.
    """

    model_config = ConfigDict(extra="forbid")

    items:                   list[FoundDoc] = Field(default_factory=list)
    dropped_below_threshold: int            = Field(default=0, ge=0, examples=[1])
