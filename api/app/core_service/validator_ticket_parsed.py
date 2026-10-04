from pathlib import Path

from pydantic import ValidationError

from app.core_model.ticket_parsed import ParsedTicket
from app.core_model.validation_parsed_file import FileVerdict
from app.core_model.validation_parsed_report import ValidationReport
from app.core_util.validation_text import describe_validation_error


def validate_file(path: Path) -> FileVerdict:         # np. Path("data/unsafe/parsed/33644.json")
    """
    Description:
    Waliduje jeden plik artefaktu wobec `ParsedTicket`.

    Każdą wadę raportujemy, zamiast rzucać wyjątek: jeden nieczytelny plik nie może przerwać
    przebiegu po całym korpusie, bo ten przebieg robi się właśnie po to, żeby zobaczyć wszystkie
    problemy naraz.

    Example args:
        path=Path("data/unsafe/parsed/33644.json")

    Example result:
        FileVerdict(path=Path("data/unsafe/parsed/33644.json"), errors=[])
    """
    try:
        ParsedTicket.model_validate_json(path.read_text(encoding="utf-8"))
    # Wadliwy JSON też trafia tutaj: `model_validate_json` zgłasza go jako ValidationError typu
    # `json_invalid`, więc osobne łapanie json.JSONDecodeError byłoby martwym kodem.
    except ValidationError as exc:
        return FileVerdict(path=path, errors=describe_validation_error(exc))
    # Rzucany przez read_text(), zanim pydantic w ogóle zobaczy treść.
    except UnicodeDecodeError as exc:
        return FileVerdict(path=path, errors=[f"plik nie jest tekstem UTF-8: {exc}"])

    return FileVerdict(path=path, errors=[])


def validate_directory(directory: Path) -> ValidationReport:   # np. Path("data/unsafe/parsed")
    """
    Description:
    Waliduje każdy plik `*.json` w katalogu, w kolejności posortowanej, żeby dwa przebiegi po tym
    samym korpusie dawały porównywalne raporty.

    Pusty katalog daje pusty, zaliczony raport — `data/unsafe/parsed/` jest legalnie pusty aż do
    masowego importu (p. 31), i to nie jest błąd.

    Example args:
        directory=Path("data/unsafe/parsed")

    Example result:
        ValidationReport(verdicts=[FileVerdict(path=…, errors=[]), …])

    Raises:
        NotADirectoryError: ścieżka nie istnieje albo nie jest katalogiem
    """
    if not directory.is_dir():
        raise NotADirectoryError(f"nie jest katalogiem: {directory}")

    files = sorted(directory.glob("*.json"))

    return ValidationReport(verdicts=[validate_file(path) for path in files])
