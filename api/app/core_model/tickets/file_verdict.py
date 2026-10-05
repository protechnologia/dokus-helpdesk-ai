from pathlib import Path

from pydantic import BaseModel, Field


class FileVerdict(BaseModel):
    """
    Description:
    Wynik walidacji jednego pliku artefaktu. Niesie powód, a nie samą wartość logiczną: przebieg
    po korpusie robi się po to, żeby dowiedzieć się, CO jest nie tak, a nie ile plików odpadło.
    """

    path:   Path      = Field(examples=[Path("data/unsafe/parsed/33644.json")])
    errors: list[str] = Field(default_factory=list, examples=[["resolution: spoza słownika"]])

    @property
    def ok(self) -> bool:
        """
        Description:
        Mówi, czy plik jest poprawnym artefaktem.

        Example args:
            (brak)

        Example result:
            True
        """
        return not self.errors
