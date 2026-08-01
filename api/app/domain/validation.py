from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.domain.ticket import ParsedTicket


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


class ValidationReport(BaseModel):
    """
    Description:
    Result of validating a whole directory of artifacts.

    Flow:
        1. `validate_directory()` walks the *.json files in a stable order.
        2. Each file yields a `FileVerdict`, valid or not.
        3. The caller (CLI, later the batch import of stage 10) prints them and decides the exit
           code — the domain reports, it does not print and does not exit.
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


def _describe(error: ValidationError) -> list[str]:   # e.g. ValidationError with 2 errors
    """
    Description:
    Flattens a pydantic error into one readable line per problem. The location is spelled out
    because a corpus-wide run produces hundreds of these, and "resolution: …" is actionable while
    a raw pydantic dump is not.

    Example args:
        error=ValidationError(...)

    Example result:
        ["resolution: Value error, resolution='zamkniete' spoza słownika"]
    """
    lines: list[str] = []

    for entry in error.errors():
        # Model-level validators report an empty location; name them for what they are.
        location = ".".join(str(part) for part in entry["loc"]) or "rekord"
        lines.append(f"{location}: {entry['msg']}")

    return lines


def validate_file(path: Path) -> FileVerdict:         # e.g. Path("data/parsed/33644.json")
    """
    Description:
    Validates one artifact file against `ParsedTicket`.

    Every defect is reported rather than raised: a single unreadable file must not abort a run
    over the whole corpus, because the reason for running it is to see every problem at once.

    Example args:
        path=Path("data/parsed/33644.json")

    Example result:
        FileVerdict(path=Path("data/parsed/33644.json"), errors=[])
    """
    try:
        ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
    # Malformed JSON arrives here too: `model_validate_json` reports it as a ValidationError of
    # type `json_invalid`, so catching json.JSONDecodeError separately would be dead code.
    except ValidationError as exc:
        return FileVerdict(path=path, errors=_describe(exc))
    # Raised by read_text(), before pydantic ever sees the content.
    except UnicodeDecodeError as exc:
        return FileVerdict(path=path, errors=[f"plik nie jest tekstem UTF-8: {exc}"])

    return FileVerdict(path=path, errors=[])


def validate_directory(directory: Path) -> ValidationReport:   # e.g. Path("data/parsed")
    """
    Description:
    Validates every `*.json` file in a directory, in sorted order so two runs over the same corpus
    produce comparable reports.

    An empty directory yields an empty, passing report — `data/parsed/` is legitimately empty
    until the batch run of stage 10, and that is not an error.

    Example args:
        directory=Path("data/parsed")

    Example result:
        ValidationReport(verdicts=[FileVerdict(path=…, errors=[]), …])

    Raises:
        NotADirectoryError: the path does not exist or is not a directory
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"nie jest katalogiem: {directory}")

    files = sorted(directory.glob("*.json"))

    return ValidationReport(verdicts=[validate_file(path) for path in files])
