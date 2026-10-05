from pydantic import BaseModel, Field


class DocsImportReport(BaseModel):
    """
    Description:
    Co zrobił jeden import dokumentacji: ile dokumentów i sekcji trafiło do tabeli w Postgresie
    i ile fragmentów do kolekcji w Qdrancie.

    Fragmentów jest co najmniej tyle, co sekcji: krótka sekcja to jeden fragment, długa — kilka.
    """

    documents: int       = Field(examples=[2])
    sections:  int       = Field(examples=[27])
    fragments: int       = Field(examples=[41])
    # Ostrzeżenia z wczytania paczki — import ich nie wstrzymuje, ale operator ma je zobaczyć.
    warnings:  list[str] = Field(default_factory=list)
