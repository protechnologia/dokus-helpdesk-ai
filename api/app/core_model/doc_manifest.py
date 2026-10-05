from collections import Counter
from datetime import date as Date

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

from app.core_model.doc_manifest_section import DocManifestSection
from app.core_model.doc_section import DocSection


class DocManifest(BaseModel):
    """
    Description:
    Metryczka jednego dokumentu — plik `manifest.json` w jego katalogu: tytuł, wydanie i sekcje
    w kolejności dokumentu.

    Do czego:
    Wejściowa połowa kontraktu dokumentacji. Na podrozdziały dzieli człowiek z modelem przed
    wgraniem; manifest mówi, co z tego podziału wyszło, a import sprawdza go wobec plików
    w katalogu. Treści sekcji tu nie ma — każda leży w pliku `<section_id>.md` obok.

    Przykład pliku:

        {
          "document":  "Instrukcja administratora",
          "version":   "4.12",
          "date":      "2026-05-04",
          "synthetic": false,
          "sections":  [
            {
              "section_id":   "adm-kancelaria-edoreczenia",
              "chapter_path": ["Uprawnienia", "Kancelaria"],
              "title":        "Uprawnienie do kancelarii e-Doręczeń",
              "description":  "Kto i gdzie nadaje uprawnienie do kancelarii e-Doręczeń"
            }
          ]
        }
    """

    model_config = ConfigDict(extra="forbid")

    document:  str                      = Field(min_length=1, examples=["Instrukcja użytkownika"])
    version:   str                      = Field(min_length=1, examples=["4.12"])
    date:      Date | None              = Field(default=None, examples=["2026-05-04"])
    # Bez wartości domyślnej i bez zgadywania z tekstu: od tej flagi zależy, do którego indeksu
    # dokument wolno wgrać.
    synthetic: StrictBool               = Field(examples=[False])
    sections:  list[DocManifestSection] = Field(min_length=1)

    @model_validator(mode="after")
    def _reject_repeated_section_ids(self) -> "DocManifest":
        """
        Description:
        Odrzuca manifest, w którym ten sam `section_id` stoi dwa razy: obie sekcje wskazywałyby
        jeden plik, a w tabeli druga nadpisałaby pierwszą.

        Example args:
            (self, już wypełniony)

        Example result:
            Ta sama instancja, bez zmian

        Raises:
            ValueError: identyfikator sekcji powtarza się w manifeście
        """
        counts   = Counter(section.section_id for section in self.sections)
        repeated = sorted(section_id for section_id, count in counts.items() if count > 1)

        if repeated:
            raise ValueError(f"section_id powtarza się w manifeście: {', '.join(repeated)}")

        return self

    def to_sections(self) -> list[DocSection]:
        """
        Description:
        Oddaje opisy sekcji w kolejności dokumentu — każdy z tytułem i wydaniem dokumentu
        z nagłówka manifestu.

        Example args:
            (brak)

        Example result:
            [DocSection(section_id="adm-kancelaria-edoreczenia", version="4.12", …), …]
        """
        sections = [
            DocSection(
                section_id   = entry.section_id,
                document     = self.document,
                version      = self.version,
                date         = self.date,
                chapter_path = entry.chapter_path,
                title        = entry.title,
                description  = entry.description,
            )
            for entry in self.sections
        ]

        return sections
