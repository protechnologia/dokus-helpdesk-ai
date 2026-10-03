from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.model.doc_section import DocSection

# Ile sekcji da się odczytać jednym wywołaniem: dość na sprawę z kilkoma wątkami, a za mało, żeby
# model wciągnął do kontekstu całą instrukcję zamiast ją przeszukać.
MAX_SECTIONS_PER_READ = 5

SectionId = Annotated[str, Field(min_length=1)]


class ReadDocsQuery(BaseModel):
    """
    Description:
    O co agent pyta `read_docs`: identyfikatory sekcji ze spisu treści albo z wyszukiwania,
    których treść chce przeczytać.
    """

    # Nieznany argument to błąd, jak w każdym modelu zapytania.
    model_config = ConfigDict(extra="forbid")

    section_ids: list[SectionId] = Field(
        min_length = 1,
        max_length = MAX_SECTIONS_PER_READ,
        examples   = [["adm-kancelaria-edoreczenia"]],
    )


class ReadSection(BaseModel):
    """
    Description:
    Jedna odczytana sekcja dokumentacji: jej opis z metryczki i treść — dosłownie taka, jak
    w pliku `.md` sekcji.
    """

    model_config = ConfigDict(extra="forbid")

    section: DocSection
    text:    str = Field(min_length=1, examples=["Uprawnienie do kancelarii nadaje administrator…"])


class ReadDocsResult(BaseModel):
    """
    Description:
    Co dał jeden odczyt `read_docs`: wszystkie żądane sekcje, w kolejności żądania. Wynik
    częściowy nie istnieje — brak którejkolwiek sekcji to błąd (`UnknownSectionError`).
    """

    model_config = ConfigDict(extra="forbid")

    items: list[ReadSection] = Field(default_factory=list)
