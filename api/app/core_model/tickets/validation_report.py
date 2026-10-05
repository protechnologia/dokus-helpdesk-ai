from pydantic import BaseModel, Field

from app.core_model.tickets.file_verdict import FileVerdict


class ValidationReport(BaseModel):
    """
    Description:
    Wynik walidacji całego katalogu artefaktów.

    Flow:
        1. `validate_directory()` przechodzi po plikach `*.json` w stałej kolejności.
        2. Każdy plik daje `FileVerdict`, poprawny albo nie.
        3. Wołający (komenda, później masowy import — p. 31) wypisuje werdykty i ustala kod
           wyjścia; serwis raportuje, nie wypisuje i nie kończy procesu.
    """

    verdicts: list[FileVerdict] = Field(default_factory=list)

    @property
    def failed(self) -> list[FileVerdict]:
        """
        Description:
        Oddaje tylko werdykty z błędami, w kolejności czytania plików.

        Example args:
            (brak)

        Example result:
            [FileVerdict(path=Path("data/unsafe/parsed/33644.json"), errors=["resolution: …"])]
        """
        return [verdict for verdict in self.verdicts if not verdict.ok]

    @property
    def ok(self) -> bool:
        """
        Description:
        Mówi, czy każdy plik w katalogu jest poprawnym artefaktem.

        Example args:
            (brak)

        Example result:
            False
        """
        return not self.failed
