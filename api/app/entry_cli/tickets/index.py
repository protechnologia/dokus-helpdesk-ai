from pathlib import Path

import typer

from app.entry_cli.tickets.common import (
    CORPUS_DIR_HELP,
    VERBOSE_DROPS_HELP,
    corpus_or_default,
    execute_index_build,
)

HELP = "Zbuduj indeksy z korpusu (karty i wątki), nie kasując istniejących."


def index_artifacts(
    directory: Path | None = typer.Argument(None, help=CORPUS_DIR_HELP),
    verbose:   bool        = typer.Option(False, "--verbose", "-v", help=VERBOSE_DROPS_HELP),
) -> None:
    """
    Description:
    `helpdesk tickets index` — indeksuje karty korpusu do istniejącej kolekcji, a wątki kart
    przyjętych do tabeli wątków, nadpisując punkty i wiersze zgłoszeń, które już tam są. Ponowne
    uruchomienie jest bezpieczne: id punktu i klucz wiersza wynikają z `ticket_id`, więc to samo
    zgłoszenie trafia w to samo miejsce, zamiast się dublować. Korpus bez `anonymized/` (golden
    set) buduje same karty.

    Example args:
        directory=None  # korpus z TICKETS_CORPUS_DIR
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord
    """
    execute_index_build(corpus_or_default(directory), drop_first=False, verbose=verbose)
