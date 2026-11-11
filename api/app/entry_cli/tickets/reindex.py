from pathlib import Path

import typer

from app.config import Settings
from app.entry_cli.tickets.common import (
    CARDS_DIR_HELP,
    VERBOSE_DROPS_HELP,
    cards_dir_or_default,
    execute_index_build,
)

HELP = "Skasuj kolekcję i zbuduj ją od zera."


def reindex_artifacts(
    directory: Path | None = typer.Argument(None, help=CARDS_DIR_HELP),
    yes:       bool        = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
    verbose:   bool        = typer.Option(False, "--verbose", "-v", help=VERBOSE_DROPS_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets reindex` — kasuje kolekcję i buduje ją od zera z artefaktów.

    Pyta przed zniszczeniem czegokolwiek, chyba że podano `--yes`. Indeks da się odbudować
    z `data/unsafe/corpus/cards/` tą samą komendą (zasada 8), więc ryzykiem jest przestój, nie
    utrata danych. Katalogu, którego nie ma albo w którym nie ma kart, indekser nie przyjmie,
    zanim cokolwiek skasuje.

    Example args:
        directory=None  # karty korpusu z TICKETS_CORPUS_DIR
        yes=False
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord

    Raises:
        typer.Exit: kod 1, gdy operator odmówi potwierdzenia
    """
    settings  = Settings()
    directory = cards_dir_or_default(directory)

    # Pytanie nazywa kolekcję i katalog, bo obie wartości mogą przyjść z konfiguracji —
    # potwierdzenie niszczącej operacji bez nazwania celu to sposób na skasowanie nie tego indeksu.
    question = f"Skasować kolekcję '{settings.qdrant_collection}' i zbudować ją z {directory}?"

    if not yes and not typer.confirm(question):
        typer.echo("Przerwano.")
        raise typer.Exit(code=1)

    execute_index_build(directory, drop_first=True, verbose=verbose)
