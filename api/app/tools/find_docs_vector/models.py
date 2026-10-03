from pydantic import BaseModel, ConfigDict, Field

from app.model.doc_section import DocSection


class FindDocsVectorQuery(BaseModel):
    """
    Description:
    O co agent pyta `find_docs_vector`: zagadnienie albo słowa kluczowe funkcji czy procedury,
    której wyjaśnienia potrzebuje. Dopasowywane znaczeniowo do sekcji dokumentacji.
    """

    # Nieznany argument to błąd, jak w FindTicketsVectorQuery.
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, examples=["uprawnienia kancelaria e-Doręczenia"])


class FoundSection(BaseModel):
    """
    Description:
    Jedna sekcja dokumentacji zwrócona przez `find_docs_vector`: podobieństwo, z jakim ją
    znaleziono, i jej opis z metryczki. Treści sekcji tu nie ma — daje ją `read_docs`.

    Jednostką jest zawsze sekcja z metryczki, także gdy wektor powstał z jej fragmentu: fragment
    zwija się do sekcji, więc wyszukiwanie wektorowe i tekstowe wskazują ten sam identyfikator.
    """

    model_config = ConfigDict(extra="forbid")

    score:   float = Field(examples=[0.74])
    section: DocSection


class FindDocsVectorResult(BaseModel):
    """
    Description:
    Co dało jedno wyszukiwanie `find_docs_vector`: sekcje, które przeszły próg, i liczba
    odciętych — liczona z tego samego powodu co w `FindTicketsVectorResult`.
    """

    model_config = ConfigDict(extra="forbid")

    items:                   list[FoundSection] = Field(default_factory=list)
    dropped_below_threshold: int                = Field(default=0, ge=0, examples=[1])
