import json
from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field

from app.model.doc_section import DocSection


class DocRow(BaseModel):
    """
    Description:
    Jeden wiersz tabeli dokumentacji — pole na każdą kolumnę, w tych samych typach co w bazie.

    Do czego:
    W tym kształcie wiersz wchodzi do tabeli i z niej wraca. Na opis sekcji z metryczki i z niego
    przechodzi się jawnie: `from_section()` przy zapisie, `to_section()` po odczycie.

    Flow:
        1. Import dokumentacji buduje wiersz z opisu sekcji, jej treści i miejsca w dokumencie.
        2. Tabela zapisuje pola wprost do kolumn o tych samych nazwach.
        3. Szukanie i odczyt oddają takie same wiersze; narzędzie bierze z nich `to_section()`
           albo `body`.
    """

    model_config = ConfigDict(extra="forbid")

    section_id:   str         = Field(min_length=1, examples=["adm-kancelaria-edoreczenia"])
    # Kolejność sekcji w dokumencie — po niej układa się spis treści.
    ordinal:      int         = Field(ge=0, examples=[0])
    document:     str         = Field(min_length=1, examples=["Instrukcja administratora"])
    version:      str         = Field(min_length=1, examples=["4.12"])
    released:     Date | None = Field(default=None, examples=["2026-05-04"])
    # Ścieżka rozdziału jako lista w JSON-ie, np. '["Uprawnienia", "Kancelaria"]'.
    chapter_path: str         = Field(examples=['["Uprawnienia", "Kancelaria"]'])
    title:        str         = Field(min_length=1, examples=["Uprawnienie do kancelarii"])
    description:  str         = Field(min_length=1, examples=["Kto nadaje uprawnienie i gdzie"])
    # Treść sekcji — dosłownie taka, jak w pliku `.md`.
    body:         str         = Field(min_length=1, examples=["Uprawnienie nadaje administrator…"])

    @classmethod
    def from_section(
        cls,
        section: DocSection,  # np. DocSection(section_id="adm-kancelaria-edoreczenia", …)
        body:    str,         # treść pliku `.md` sekcji
        ordinal: int,         # miejsce sekcji w dokumencie, od zera
    ) -> "DocRow":
        """
        Description:
        Buduje wiersz z opisu sekcji z metryczki, jej treści i miejsca w dokumencie.

        Example args:
            section=DocSection(section_id="adm-kancelaria-edoreczenia", …)
            body="Uprawnienie do kancelarii e-Doręczeń nadaje administrator…"
            ordinal=0

        Example result:
            DocRow(section_id="adm-kancelaria-edoreczenia", ordinal=0, body="Uprawnienie…", …)
        """
        row = cls(
            section_id   = section.section_id,
            ordinal      = ordinal,
            document     = section.document,
            version      = section.version,
            released     = section.date,
            chapter_path = json.dumps(section.chapter_path, ensure_ascii=False),
            title        = section.title,
            description  = section.description,
            body         = body,
        )

        return row

    def to_section(self) -> DocSection:
        """
        Description:
        Odtwarza opis sekcji z pól wiersza — bez treści.

        Example args:
            (brak)

        Example result:
            DocSection(section_id="adm-kancelaria-edoreczenia", chapter_path=["Uprawnienia"], …)
        """
        section = DocSection(
            section_id   = self.section_id,
            document     = self.document,
            version      = self.version,
            date         = self.released,
            chapter_path = json.loads(self.chapter_path),
            title        = self.title,
            description  = self.description,
        )

        return section
