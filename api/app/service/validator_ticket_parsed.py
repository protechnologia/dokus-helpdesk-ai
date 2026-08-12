from pathlib import Path

from pydantic import ValidationError

from app.model.ticket_parsed import ParsedTicket
from app.model.validation_parsed_file import FileVerdict
from app.model.validation_parsed_report import ValidationReport
from app.util.validation_text import describe_validation_error


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
        return FileVerdict(path=path, errors=describe_validation_error(exc))
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
