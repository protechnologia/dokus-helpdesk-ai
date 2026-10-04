from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field


class DocSection(BaseModel):
    """
    Description:
    Jedna sekcja dokumentacji produktu, tak jak opisuje ją metryczka dokumentu: z jakiego
    dokumentu i wydania pochodzi, gdzie w nim leży i o czym jest.

    Do czego:
    Jednostka dokumentacji w całym systemie. Jeden plik `.md` z treścią i ten opis to jedna
    sekcja, a `section_id` wskazują wszystkie narzędzia dokumentacji — listing, oba wyszukiwania
    i odczyt — więc sekcja znaleziona różnymi drogami ma zawsze ten sam identyfikator. Treści tu
    nie ma: model dostaje ją dopiero z odczytu (`read_docs`).

    Wydanie (`version`) jest wymagane, bo instrukcja do starszej wersji wprowadza w błąd tak samo
    jak odmowa obalona później nowszym zgłoszeniem (CLAUDE.md -> „Ryzyka jakości treści").
    """

    model_config = ConfigDict(extra="forbid")

    section_id:   str         = Field(min_length=1, examples=["adm-kancelaria-edoreczenia"])
    document:     str         = Field(min_length=1, examples=["Instrukcja administratora"])
    version:      str         = Field(min_length=1, examples=["4.12"])
    date:         Date | None = Field(default=None, examples=["2026-05-04"])
    chapter_path: list[str]   = Field(default_factory=list, examples=[["Uprawnienia"]])
    title:        str         = Field(min_length=1, examples=["Uprawnienie do kancelarii"])
    description:  str         = Field(min_length=1, examples=["Kto nadaje uprawnienie i gdzie"])
