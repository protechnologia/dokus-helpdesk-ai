from pathlib import Path

from pydantic import BaseModel, Field


class FileVerdict(BaseModel):
    """
    Description:
    Outcome of validating one artifact file. Carries the reason rather than a bare boolean: the
    point of running this over a corpus is learning WHAT is wrong, not how many files failed.
    """

    path:   Path      = Field(examples=[Path("data/parsed/33644.json")])
    errors: list[str] = Field(default_factory=list, examples=[["resolution: spoza słownika"]])

    @property
    def ok(self) -> bool:
        """
        Description:
        Tells whether the file is a valid artifact.

        Example args:
            (none)

        Example result:
            True
        """
        return not self.errors
