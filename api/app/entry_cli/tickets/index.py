from pathlib import Path

import typer

from app.entry_cli.tickets.common import (
    CARDS_DIR_HELP,
    VERBOSE_DROPS_HELP,
    cards_dir_or_default,
    execute_index_build,
)

HELP = "Zbuduj indeks z artefaktów, nie kasując istniejącej kolekcji."


def index_artifacts(
    directory: Path | None = typer.Argument(None, help=CARDS_DIR_HELP),
    verbose:   bool        = typer.Option(False, "--verbose", "-v", help=VERBOSE_DROPS_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets index` — indeksuje artefakty do istniejącej kolekcji, nadpisując punkty
    zgłoszeń, które już tam są. Ponowne uruchomienie jest bezpieczne: id punktu wynika
    z `ticket_id`, więc to samo zgłoszenie trafia w ten sam punkt, zamiast się dublować.

    Example args:
        directory=None  # karty korpusu z TICKETS_CORPUS_DIR
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord
    """
    execute_index_build(cards_dir_or_default(directory), drop_first=False, verbose=verbose)
