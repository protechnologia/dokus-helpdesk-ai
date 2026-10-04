from pathlib import Path

import typer

from app.config import Settings
from app.entry_cli.rag.common import execute_index_build

HELP = "Skasuj kolekcję i zbuduj ją od zera."


def reindex_artifacts(
    directory: Path = typer.Argument(Path("data/parsed"), help="Katalog z artefaktami."),
    yes:       bool = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz wszystkie odrzucone."),
) -> None:
    """
    Description:
    `helpdesk rag reindex` — kasuje kolekcję i buduje ją od zera z artefaktów.

    Pyta przed zniszczeniem czegokolwiek, chyba że podano `--yes`. Indeks da się odbudować
    z `data/parsed/` tą samą komendą (zasada 8), więc ryzykiem jest przestój, nie utrata danych —
    ale przypadkowy przebieg na pustym albo złym katalogu nie zostawi nic do przeszukania.

    Example args:
        directory=Path("data/parsed")
        yes=False
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord

    Raises:
        typer.Exit: kod 1, gdy operator odmówi potwierdzenia
    """
    settings = Settings()

    # Nazwa kolekcji pochodzi z konfiguracji, więc pytanie mówi, KTÓRA ma zniknąć — potwierdzenie
    # niszczącej operacji bez nazwania celu to sposób na skasowanie nie tego indeksu.
    if not yes and not typer.confirm(f"Skasować kolekcję '{settings.qdrant_collection}'?"):
        typer.echo("Przerwano.")
        raise typer.Exit(code=1)

    execute_index_build(directory, drop_first=True, verbose=verbose)
