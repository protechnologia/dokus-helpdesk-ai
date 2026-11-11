from pathlib import Path

import typer

from app.core_model.tickets.validation_report import ValidationReport
from app.core_service.validator_ticket_parsed import validate_directory
from app.entry_cli.tickets.common import CARDS_DIR_HELP, cards_dir_or_default

HELP = "Sprawdź pliki JSON w katalogu wobec kontraktu ParsedTicket."

# Pomoc flagi `--verbose`.
VERBOSE_HELP = "Wypisz też poprawne pliki."


def _print_report(
    report:  ValidationReport,  # np. ValidationReport(verdicts=[…])
    verbose: bool,              # np. False
) -> None:
    """
    Description:
    Wypisuje raport. Błędy zawsze, poprawne pliki tylko z `--verbose`, żeby przebieg po całym
    korpusie pokazywał problemy, zamiast przewijać je poza ekran.

    Example args:
        report=ValidationReport(verdicts=[…])
        verbose=False

    Example result:
        None — linie per plik i podsumowanie na stdout
    """
    for verdict in report.verdicts:
        if verdict.ok:
            # Poprawny plik to szum przy przebiegu po korpusie; liczy się tylko na życzenie.
            if verbose:
                typer.echo(f"OK   {verdict.path.name}")
            continue

        typer.echo(f"BŁĄD {verdict.path.name}")

        for error in verdict.errors:
            typer.echo(f"       {error}")

    checked = len(report.verdicts)
    failed  = len(report.failed)

    typer.echo(f"\nSprawdzono {checked}, błędnych {failed}.")


def validate_artifacts(
    directory: Path | None = typer.Argument(None, help=CARDS_DIR_HELP),
    verbose:   bool        = typer.Option(False, "--verbose", "-v", help=VERBOSE_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets validate` — sprawdza katalog artefaktów i kończy się kodem niezerowym, gdy
    coś jest nie tak, więc komenda działa jako bramka w potoku, a nie tylko dla czytającego.

    Cienki adapter nad `validate_directory()`: logiki walidacji tu nie ma, dzięki czemu masowy
    import (p. 31) użyje tego samego sprawdzenia bez przechodzenia przez CLI.

    Example args:
        directory=None  # karty korpusu z TICKETS_CORPUS_DIR
        verbose=False

    Example result:
        wypisuje raport; kod 0, gdy wszystkie pliki są poprawne, 1 w przeciwnym razie

    Raises:
        typer.Exit: kod 1 przy błędnych plikach, kod 2, gdy katalog nie istnieje
    """
    try:
        report = validate_directory(cards_dir_or_default(directory))
    except NotADirectoryError as exc:
        # Kod 2 oddziela „wskazałeś nic" od „artefakty są zepsute" — potok musi odróżnić złą
        # konfigurację od rzeczywistej porażki.
        typer.echo(f"BŁĄD: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    _print_report(report, verbose)

    if not report.ok:
        raise typer.Exit(code=1)
