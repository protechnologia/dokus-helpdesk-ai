from pathlib import Path

import typer

from app.config import Settings
from app.entry_cli.tickets.common import (
    CORPUS_DIR_HELP,
    VERBOSE_DROPS_HELP,
    corpus_or_default,
    execute_index_build,
)

HELP = "Skasuj indeksy zgłoszeń (kolekcję kart, tabelę wątków) i zbuduj je od zera."


def reindex_artifacts(
    directory: Path | None = typer.Argument(None, help=CORPUS_DIR_HELP),
    yes:       bool        = typer.Option(False, "--yes", help="Nie pytaj o potwierdzenie."),
    verbose:   bool        = typer.Option(False, "--verbose", "-v", help=VERBOSE_DROPS_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets reindex` — kasuje kolekcję kart i, gdy korpus ma `anonymized/`, tabelę
    wątków, i buduje je od zera z korpusu. Pyta przed zniszczeniem czegokolwiek, chyba że
    podano `--yes`. Indeksy da się odbudować z plików korpusu tą samą komendą (zasada 8), więc
    ryzykiem jest przestój, nie utrata danych. Korpusu bez kart albo z kartą bez wątku indekser
    nie przyjmie, zanim cokolwiek skasuje.

    Example args:
        directory=None  # korpus z TICKETS_CORPUS_DIR
        yes=False
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord

    Raises:
        typer.Exit: kod 1, gdy operator odmówi potwierdzenia
    """
    settings = Settings()
    corpus   = corpus_or_default(directory)

    # Pytanie nazywa to, co zniknie, i skąd przyjdzie nowe, bo wszystko może przyjść
    # z konfiguracji — potwierdzenie niszczącej operacji bez nazwania celu to sposób na
    # skasowanie nie tego indeksu. Tabelę wątków wymienia tylko wtedy, gdy będzie kasowana.
    collection = settings.qdrant_collection
    table      = settings.postgres_tickets_table

    if corpus.anonymized_dir.is_dir():
        question = (
            f"Skasować kolekcję '{collection}' i tabelę '{table}' i zbudować je z {corpus.root}?"
        )
    else:
        question = (
            f"Skasować kolekcję '{collection}' i zbudować ją z {corpus.cards_dir}? "
            f"Tabela '{table}' zostaje: w {corpus.root} nie ma anonymized/."
        )

    if not yes and not typer.confirm(question):
        typer.echo("Przerwano.")
        raise typer.Exit(code=1)

    execute_index_build(corpus, drop_first=True, verbose=verbose)
