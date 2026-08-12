from pydantic import BaseModel, Field

from app.model.validation_parsed_file import FileVerdict


class ValidationReport(BaseModel):
    """
    Description:
    Result of validating a whole directory of artifacts.

    Flow:
        1. `validate_directory()` walks the *.json files in a stable order.
        2. Each file yields a `FileVerdict`, valid or not.
        3. The caller (CLI, later the batch import of stage 10) prints them and decides the exit
           code — the service reports, it does not print and does not exit.
    """

    verdicts: list[FileVerdict] = Field(default_factory=list)

    @property
    def failed(self) -> list[FileVerdict]:
        """
        Description:
        Returns only the verdicts that carry errors, in the order the files were read.

        Example args:
            (none)

        Example result:
            [FileVerdict(path=Path("data/parsed/33644.json"), errors=["resolution: …"])]
        """
        return [verdict for verdict in self.verdicts if not verdict.ok]

    @property
    def ok(self) -> bool:
        """
        Description:
        Tells whether every file in the directory is a valid artifact.

        Example args:
            (none)

        Example result:
            False
        """
        return not self.failed
