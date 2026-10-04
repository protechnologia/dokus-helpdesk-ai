from pathlib import Path

import typer

from app.entry_cli.rag.common import execute_index_build

HELP = "Zbuduj indeks z artefaktów, nie kasując istniejącej kolekcji."


def index_artifacts(
    directory: Path = typer.Argument(Path("data/unsafe/parsed"), help="Katalog z artefaktami."),
    verbose:   bool = typer.Option(False, "--verbose", "-v", help="Wypisz wszystkie odrzucone."),
) -> None:
    """
    Description:
    `helpdesk rag index` — indeksuje artefakty do istniejącej kolekcji, nadpisując punkty
    zgłoszeń, które już tam są. Ponowne uruchomienie jest bezpieczne: id punktu wynika
    z `ticket_id`, więc to samo zgłoszenie trafia w ten sam punkt, zamiast się dublować.

    Example args:
        directory=Path("data/unsafe/parsed")
        verbose=False

    Example result:
        wypisuje raport przebiegu; kod 0, gdy zaindeksowano co najmniej jeden rekord
    """
    execute_index_build(directory, drop_first=False, verbose=verbose)
